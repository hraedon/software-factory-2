from __future__ import annotations

import random
import threading
import time
import uuid
import weakref

import structlog

from factory.config import FactoryConfig
from factory.constants import (
    ACTOR_KIND_AGENT,
    CUSTOM_FIELD_AC_IDS,
    CUSTOM_FIELD_DEPENDENCY_REFS,
    CUSTOM_FIELD_INTERFACE_REF,
    CUSTOM_FIELD_REVIEW_FINDINGS,
    CUSTOM_FIELD_REVIEW_REF,
    CUSTOM_FIELD_SPEC_SECTION,
    CUSTOM_FIELD_TEST_SUITE_REF,
    CUSTOM_FIELD_UPSTREAM_REVISION_OF,
    LINK_TYPE_IMPLEMENTS,
    STATE_LOCKED,
    WORK_ITEM_TYPE_JURY,
)
from factory.gate import GateResult
from factory.idempotency import make_event_id
from factory.router import Route
from factory.runtime import PipelineRuntime

log = structlog.get_logger()

# ---------------------------------------------------------------------------
# Dedup lock registry (BC-190)
#
# Ensures that two threads calling _ensure_downstream_item for the same
# (source_id, downstream_type) pair cannot both see "no item found" and
# create duplicates.  A WeakValue dictionary keeps the registry from growing
# unboundedly: once no thread holds a reference to the lock, it is garbage-
# collected automatically.
#
# Limitation: guards races within a single scheduler process only.  Multi-
# process deployments would require a distributed lock (e.g. a Postgres
# advisory lock).  Acceptable for Phase 5 single-scheduler mode.
# ---------------------------------------------------------------------------
_dedup_lock_registry: weakref.WeakValueDictionary[tuple, threading.Lock] = (
    weakref.WeakValueDictionary()
)
_dedup_registry_meta_lock = threading.Lock()


def _get_dedup_lock(source_id: str, downstream_type: str) -> threading.Lock:
    """Return a per-(source_id, downstream_type) Lock, creating it if absent."""
    key = (source_id, downstream_type)
    with _dedup_registry_meta_lock:
        lock = _dedup_lock_registry.get(key)
        if lock is None:
            lock = threading.Lock()
            _dedup_lock_registry[key] = lock
        return lock


# ---------------------------------------------------------------------------
# Existence cache — avoids repeated O(N) regista scans for downstream items.
#
# Maps (source_id, downstream_type) → True once a downstream item is known to
# exist.  A hit means we can skip the O(N) paginated scan entirely.  Misses
# still fall through to the full scan (cache is write-on-create, not on
# read, so a fresh process starts empty).
#
# Invalidation: the entry is only set to True after a successful create or
# after finding the item in the scan.  False-positives are impossible; a
# stale False just means we pay the scan cost once more.
# ---------------------------------------------------------------------------
_EXISTENCE_CACHE_MAXSIZE = 4096
_existence_cache: dict[tuple, bool] = {}
_existence_cache_lock = threading.Lock()


def _cache_exists(source_id: str, downstream_type: str) -> bool:
    with _existence_cache_lock:
        return _existence_cache.get((source_id, downstream_type), False)


def _cache_mark_exists(source_id: str, downstream_type: str) -> None:
    with _existence_cache_lock:
        if len(_existence_cache) >= _EXISTENCE_CACHE_MAXSIZE:
            _existence_cache.pop(next(iter(_existence_cache)), None)
        _existence_cache[(source_id, downstream_type)] = True


def run_scheduler(config: FactoryConfig) -> None:
    from regista import Regista

    sub = Regista(config.dsn, config.project_name, config.hmac_key_path)
    runtime = PipelineRuntime(sub=sub, config=config)
    try:
        scheduler_loop(runtime)
    finally:
        sub.close()


def scheduler_loop(runtime: PipelineRuntime) -> None:
    config = runtime.config
    poll_interval = config.poll_interval_seconds
    shutting_down = False

    import signal as signal_mod

    def _handle_signal(signum, frame):
        nonlocal shutting_down
        shutting_down = True
        log.info("scheduler_shutdown_requested", signal=signum)

    signal_mod.signal(signal_mod.SIGTERM, _handle_signal)
    signal_mod.signal(signal_mod.SIGINT, _handle_signal)

    while not shutting_down:
        try:
            _poll_handoffs(runtime)
        except Exception:
            log.exception("scheduler_poll_error")
        if not shutting_down:
            time.sleep(poll_interval)

    log.info("scheduler_draining", drain_cycles=3)
    for i in range(3):
        try:
            _poll_handoffs(runtime)
        except Exception:
            log.exception("scheduler_drain_error", cycle=i)
        time.sleep(poll_interval)

    log.info("scheduler_loop_exiting")


def _poll_handoffs(runtime: PipelineRuntime) -> None:
    sub = runtime.sub
    config = runtime.config
    # BC-190: randomise iteration order each cycle so a noisy upstream stage
    # cannot permanently starve downstream stages of poll attention.
    topology = list(config.stage_topology)
    random.shuffle(topology)
    for handoff in topology:
        page = sub.query_work_items(
            workflow_name=config.workflow_name,
            workflow_version=config.workflow_version,
            current_states=[handoff.source_state],
            page_size=config.query_page_size,
        )
        for wi in page.items:
            if wi.work_item_type != handoff.source_type:
                continue
            _ensure_downstream_item(runtime, wi, handoff)


def _ensure_downstream_item(
    runtime: PipelineRuntime,
    source_wi,
    handoff,
) -> None:
    sub = runtime.sub
    config = runtime.config
    next_type = handoff.target_type
    link_type = handoff.link_type
    next_role = config.role_for_type(next_type)
    if next_role is None:
        log.warning(
            "no_role_for_type",
            work_item_type=next_type,
        )
        return
    additional_links = handoff.additional_links
    ref_field = handoff.ref_field

    source_id_str = str(source_wi.work_item_id)

    # BC-190: acquire per-(source_id, downstream_type) lock before the
    # existence check so two concurrent callers cannot both observe "not found"
    # and both proceed to create.
    dedup_lock = _get_dedup_lock(source_id_str, next_type)
    with dedup_lock:
        if ref_field:
            # BC-190: fast path — if we already know this downstream exists,
            # skip the O(N) paginated scan entirely.
            if _cache_exists(source_id_str, next_type):
                return

            found = False
            cursor = None
            while not found:
                page = sub.query_work_items(
                    workflow_name=config.workflow_name,
                    workflow_version=config.workflow_version,
                    work_item_types=[next_type],
                    page_size=config.query_page_size,
                    cursor=cursor,
                )
                for item in page.items:
                    item_ref = (item.custom_fields or {}).get(ref_field)
                    if item_ref and str(item_ref) == source_id_str:
                        found = True
                        break
                if found:
                    _cache_mark_exists(source_id_str, next_type)
                    return
                if not page.has_more:
                    break
                cursor = page.cursor

        custom = source_wi.custom_fields or {}
        extra: dict = {}
        if ref_field:
            extra[ref_field] = source_id_str

        for field_name in handoff.propagate_fields:
            field_val = custom.get(field_name)
            if field_val:
                extra[field_name] = field_val

        dep_refs = custom.get(CUSTOM_FIELD_DEPENDENCY_REFS) or []
        if isinstance(dep_refs, str):
            dep_refs = [dep_refs]

        if dep_refs and not _all_dep_specs_locked(sub, dep_refs):
            return

        # Only propagate dependency_refs if the downstream work_item_type
        # actually declares it (jury/integration/outcome_verification do not).
        _has_dep_field = _downstream_has_field(sub, config, next_type, CUSTOM_FIELD_DEPENDENCY_REFS)
        if dep_refs and _has_dep_field:
            extra[CUSTOM_FIELD_DEPENDENCY_REFS] = dep_refs

        downstream, _ = sub.create_work_item(
            workflow_name=config.workflow_name,
            work_item_type=next_type,
            actor_id=config.scheduler_actor_id,
            actor_kind=ACTOR_KIND_AGENT,
            actor_metadata={"role": next_role},
            custom_fields={
                CUSTOM_FIELD_SPEC_SECTION: custom.get(CUSTOM_FIELD_SPEC_SECTION, ""),
                CUSTOM_FIELD_AC_IDS: custom.get(CUSTOM_FIELD_AC_IDS, []),
                **extra,
            },
            event_id=make_event_id(
                source_wi.work_item_id, "create_work_item", 0, extra=f"{next_type}"
            ),
        )

        # BC-190: mark existence in cache immediately after create so any
        # subsequent call within this process skips the scan.
        if ref_field:
            _cache_mark_exists(source_id_str, next_type)

        sub.create_link(
            from_work_item_id=downstream.work_item_id,
            to_work_item_id=source_wi.work_item_id,
            link_type=link_type,
            actor_id=config.scheduler_actor_id,
            actor_kind=ACTOR_KIND_AGENT,
            event_id=make_event_id(downstream.work_item_id, "create_link", 0, extra=link_type),
        )

        for extra_link_type in additional_links:
            if extra_link_type == LINK_TYPE_IMPLEMENTS:
                pf = handoff.propagate_fields
                interface_ref = None
                if CUSTOM_FIELD_INTERFACE_REF in pf:
                    interface_ref = custom.get(CUSTOM_FIELD_INTERFACE_REF)
                if interface_ref:
                    import uuid as _uuid

                    sub.create_link(
                        from_work_item_id=downstream.work_item_id,
                        to_work_item_id=_uuid.UUID(interface_ref),
                        link_type=LINK_TYPE_IMPLEMENTS,
                        actor_id=config.scheduler_actor_id,
                        actor_kind=ACTOR_KIND_AGENT,
                        event_id=make_event_id(
                            downstream.work_item_id,
                            "create_link",
                            0,
                            extra=f"{LINK_TYPE_IMPLEMENTS}",
                        ),
                    )

        log.info(
            "handoff_created",
            source_id=source_id_str,
            source_type=source_wi.work_item_type,
            downstream_id=str(downstream.work_item_id),
            downstream_type=next_type,
        )


def _all_dep_specs_locked(sub, dep_refs: list[str]) -> bool:
    import uuid as _uuid

    for ref in dep_refs:
        try:
            dep_wi = sub.get_work_item(_uuid.UUID(ref))
        except Exception:
            log.warning("_all_dep_specs_locked_error", ref=ref, exc_info=True)
            return False
        if not dep_wi or dep_wi.current_state != STATE_LOCKED:
            return False
    return True


def _downstream_has_field(sub, config: FactoryConfig, work_item_type: str, field_name: str) -> bool:
    """Return True if the workflow defines field_name for work_item_type."""
    try:
        wf = sub.get_workflow(config.workflow_name, config.workflow_version)
        for wit in wf.work_item_types:
            if wit.name == work_item_type:
                return any(cf.name == field_name for cf in wit.custom_fields)
    except Exception:
        log.warning(
            "_downstream_has_field_query_failed",
            work_item_type=work_item_type,
            field_name=field_name,
            exc_info=True,
        )
    return False


def ensure_upstream_revision(
    runtime: PipelineRuntime,
    source_wi,
    route: Route,
    gate_result: GateResult | None = None,
) -> None:
    sub = runtime.sub
    config = runtime.config
    if not route.create_upstream_revision or not route.upstream_type:
        return

    upstream_type = route.upstream_type
    upstream_role = config.role_for_type(upstream_type)
    if upstream_role is None:
        log.warning(
            "upstream_no_role",
            upstream_type=upstream_type,
        )
        return

    source_custom = source_wi.custom_fields or {}
    existing_revision = source_custom.get(CUSTOM_FIELD_UPSTREAM_REVISION_OF)
    if existing_revision:
        log.info(
            "upstream_revision_exists",
            source_id=str(source_wi.work_item_id),
            existing=existing_revision,
        )
        return

    existing_page = sub.query_work_items(
        workflow_name=config.workflow_name,
        work_item_types=[upstream_type],
        custom_field_filters={CUSTOM_FIELD_UPSTREAM_REVISION_OF: str(source_wi.work_item_id)},
        page_size=1,
    )
    if existing_page.items:
        log.info(
            "upstream_revision_duplicate",
            source_id=str(source_wi.work_item_id),
            existing_id=str(existing_page.items[0].work_item_id),
        )
        return

    custom: dict = {
        CUSTOM_FIELD_SPEC_SECTION: source_custom.get(CUSTOM_FIELD_SPEC_SECTION, ""),
        CUSTOM_FIELD_AC_IDS: source_custom.get(CUSTOM_FIELD_AC_IDS, []),
        CUSTOM_FIELD_UPSTREAM_REVISION_OF: str(source_wi.work_item_id),
    }

    dep_refs = source_custom.get(CUSTOM_FIELD_DEPENDENCY_REFS) or []
    if isinstance(dep_refs, str):
        dep_refs = [dep_refs]
    if dep_refs:
        custom[CUSTOM_FIELD_DEPENDENCY_REFS] = dep_refs

    interface_ref = source_custom.get(CUSTOM_FIELD_INTERFACE_REF)
    test_suite_ref = source_custom.get(CUSTOM_FIELD_TEST_SUITE_REF)

    if (
        not interface_ref or not test_suite_ref
    ) and source_wi.work_item_type == WORK_ITEM_TYPE_JURY:
        review_ref = source_custom.get(CUSTOM_FIELD_REVIEW_REF)
        if review_ref:
            review_wi = sub.get_work_item(uuid.UUID(review_ref))
            review_custom = review_wi.custom_fields or {}
            interface_ref = interface_ref or review_custom.get(CUSTOM_FIELD_INTERFACE_REF)
            test_suite_ref = test_suite_ref or review_custom.get(CUSTOM_FIELD_TEST_SUITE_REF)

    if interface_ref:
        custom[CUSTOM_FIELD_INTERFACE_REF] = interface_ref

    if test_suite_ref:
        custom[CUSTOM_FIELD_TEST_SUITE_REF] = test_suite_ref

    context_key = route.upstream_context_key
    if context_key:
        # Prefer structured findings from gate_result.routing_fields (BC-185).
        # Fall back to building from route.diagnostics if routing_fields is absent
        # (e.g. legacy call sites or gate evaluators that emit no routing_fields).
        if gate_result is not None and gate_result.routing_fields.get(CUSTOM_FIELD_REVIEW_FINDINGS):
            custom[CUSTOM_FIELD_REVIEW_FINDINGS] = gate_result.routing_fields[
                CUSTOM_FIELD_REVIEW_FINDINGS
            ]
        elif route.diagnostics:
            custom[CUSTOM_FIELD_REVIEW_FINDINGS] = {
                "source_wi": str(source_wi.work_item_id),
                "source_type": source_wi.work_item_type,
                "findings": route.diagnostics,
            }

    upstream_wi, _ = sub.create_work_item(
        workflow_name=config.workflow_name,
        work_item_type=upstream_type,
        actor_id=config.scheduler_actor_id,
        actor_kind=ACTOR_KIND_AGENT,
        actor_metadata={"role": upstream_role, "revision_of": str(source_wi.work_item_id)},
        custom_fields=custom,
        event_id=make_event_id(
            source_wi.work_item_id, "create_work_item", 0, extra=f"revision-{upstream_type}"
        ),
    )

    log.info(
        "upstream_revision_created",
        source_id=str(source_wi.work_item_id),
        source_type=source_wi.work_item_type,
        upstream_id=str(upstream_wi.work_item_id),
        upstream_type=upstream_type,
    )


def _main(argv: list[str] | None = None) -> None:
    import argparse

    from factory.config import load_config

    parser = argparse.ArgumentParser(description="Software Factory v2 - Scheduler")
    parser.add_argument("--config", type=str, default=None, help="Path to config YAML")
    args = parser.parse_args(argv)
    config = load_config(args.config)
    run_scheduler(config)


def main() -> None:
    _main()


if __name__ == "__main__":
    main()
