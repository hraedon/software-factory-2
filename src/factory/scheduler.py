from __future__ import annotations

import time

import structlog

from factory.config import FactoryConfig
from factory.constants import (
    ACTOR_KIND_AGENT,
    CUSTOM_FIELD_AC_IDS,
    CUSTOM_FIELD_DEPENDENCY_REFS,
    CUSTOM_FIELD_INTERFACE_REF,
    CUSTOM_FIELD_SPEC_SECTION,
    LINK_TYPE_IMPLEMENTS,
    STATE_LOCKED,
)
from factory.runtime import PipelineRuntime

log = structlog.get_logger()


def run_scheduler(config: FactoryConfig) -> None:
    from substrate import Substrate

    sub = Substrate(config.dsn, config.project_name, config.hmac_key_path)
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
    for handoff in config.stage_topology:
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

    if ref_field:
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
                if item_ref and str(item_ref) == str(source_wi.work_item_id):
                    found = True
                    break
            if found:
                return
            if not page.has_more:
                break
            cursor = page.cursor

    custom = source_wi.custom_fields or {}
    extra: dict = {}
    if ref_field:
        extra[ref_field] = str(source_wi.work_item_id)

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
    )

    sub.create_link(
        from_work_item_id=downstream.work_item_id,
        to_work_item_id=source_wi.work_item_id,
        link_type=link_type,
        actor_id=config.scheduler_actor_id,
        actor_kind=ACTOR_KIND_AGENT,
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
                )

    log.info(
        "handoff_created",
        source_id=str(source_wi.work_item_id),
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
        pass
    return False


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
