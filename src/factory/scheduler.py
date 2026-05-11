from __future__ import annotations

import time
import uuid as _uuid

import structlog

from factory.config import FactoryConfig
from factory.constants import (
    ACTOR_KIND_AGENT,
    CUSTOM_FIELD_AC_IDS,
    CUSTOM_FIELD_DEPENDENCY_REFS,
    CUSTOM_FIELD_INTERFACE_REF,
    CUSTOM_FIELD_SPEC_SECTION,
    CUSTOM_FIELD_TEST_SUITE_REF,
    LINK_TYPE_DERIVED_FROM,
    LINK_TYPE_IMPLEMENTS,
    LINK_TYPE_TESTED_BY,
    ROLE_IMPLEMENTER,
    ROLE_TEST_AUTHOR,
    STATE_LOCKED,
    WORK_ITEM_TYPE_IMPLEMENTATION,
    WORK_ITEM_TYPE_INTERFACE_SPEC,
    WORK_ITEM_TYPE_TEST_SUITE,
)
from factory.runtime import PipelineRuntime

log = structlog.get_logger()

_STAGE_HANDOFF = {
    (WORK_ITEM_TYPE_INTERFACE_SPEC, STATE_LOCKED): {
        "next_type": WORK_ITEM_TYPE_TEST_SUITE,
        "link_type": LINK_TYPE_DERIVED_FROM,
        "next_role": ROLE_TEST_AUTHOR,
    },
    (WORK_ITEM_TYPE_TEST_SUITE, STATE_LOCKED): {
        "next_type": WORK_ITEM_TYPE_IMPLEMENTATION,
        "link_type": LINK_TYPE_TESTED_BY,
        "additional_links": [LINK_TYPE_IMPLEMENTS],
        "next_role": ROLE_IMPLEMENTER,
    },
}


def run_scheduler(config: FactoryConfig) -> None:
    from substrate import Substrate

    sub = Substrate(config.dsn, config.project_name, config.hmac_key_path)
    runtime = PipelineRuntime(sub=sub, config=config)
    try:
        scheduler_loop(runtime)
    finally:
        sub.close()


def scheduler_loop(runtime: PipelineRuntime) -> None:
    sub = runtime.sub
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
        for (source_type, source_state), handoff in _STAGE_HANDOFF.items():
            page = sub.query_work_items(
                workflow_name=config.workflow_name,
                workflow_version=config.workflow_version,
                current_states=[source_state],
                page_size=config.query_page_size,
            )
            for wi in page.items:
                if wi.work_item_type != source_type:
                    continue
                _ensure_downstream_item(runtime, wi, handoff)

        if not shutting_down:
            time.sleep(poll_interval)
    log.info("scheduler_loop_exiting")


def _ensure_downstream_item(
    runtime: PipelineRuntime,
    source_wi,
    handoff: dict,
) -> None:
    sub = runtime.sub
    config = runtime.config
    next_type = handoff["next_type"]
    link_type = handoff["link_type"]
    next_role = handoff["next_role"]
    additional_links = handoff.get("additional_links", [])

    ref_field = _ref_field_for(next_type)
    if ref_field:
        existing = sub.query_work_items(
            workflow_name=config.workflow_name,
            workflow_version=config.workflow_version,
            work_item_types=[next_type],
            page_size=config.query_page_size,
        )
        for item in existing.items:
            item_ref = (item.custom_fields or {}).get(ref_field)
            if item_ref and str(item_ref) == str(source_wi.work_item_id):
                return

    custom = source_wi.custom_fields or {}
    ref_field = _ref_field_for(next_type)
    extra = {}
    if ref_field:
        extra[ref_field] = str(source_wi.work_item_id)
    if next_type == WORK_ITEM_TYPE_IMPLEMENTATION:
        iface_ref = custom.get(CUSTOM_FIELD_INTERFACE_REF)
        if iface_ref:
            extra[CUSTOM_FIELD_INTERFACE_REF] = iface_ref

    dep_refs = custom.get(CUSTOM_FIELD_DEPENDENCY_REFS) or []
    if isinstance(dep_refs, str):
        dep_refs = [dep_refs]

    if dep_refs and not _all_dep_specs_locked(sub, dep_refs):
        return

    if dep_refs:
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
            interface_ref = custom.get(CUSTOM_FIELD_INTERFACE_REF)
            if interface_ref:
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


def _ref_field_for(next_type: str) -> str | None:
    if next_type == WORK_ITEM_TYPE_TEST_SUITE:
        return CUSTOM_FIELD_INTERFACE_REF
    if next_type == WORK_ITEM_TYPE_IMPLEMENTATION:
        return CUSTOM_FIELD_TEST_SUITE_REF
    return None


def _all_dep_specs_locked(sub, dep_refs: list[str]) -> bool:
    for ref in dep_refs:
        try:
            dep_wi = sub.get_work_item(_uuid.UUID(ref))
        except Exception:
            return False
        if not dep_wi or dep_wi.current_state != STATE_LOCKED:
            return False
    return True


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
