from __future__ import annotations

import time
import uuid as _uuid

import structlog
from substrate import Substrate

from factory.config import FactoryConfig

log = structlog.get_logger()

_STAGE_HANDOFF = {
    ("interface_spec", "locked"): {
        "next_type": "test_suite",
        "link_type": "derived_from",
        "next_role": "test_author",
    },
    ("test_suite", "locked"): {
        "next_type": "implementation",
        "link_type": "tested_by",
        "additional_links": ["implements"],
        "next_role": "implementer",
    },
}


def run_scheduler(config: FactoryConfig) -> None:
    sub = Substrate(config.dsn, config.project_name, config.hmac_key_path)
    try:
        scheduler_loop(sub, config)
    finally:
        sub.close()


def scheduler_loop(sub: Substrate, config: FactoryConfig) -> None:
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
                page_size=50,
            )
            for wi in page.items:
                if wi.work_item_type != source_type:
                    continue
                _ensure_downstream_item(sub, config, wi, handoff)

        if not shutting_down:
            time.sleep(poll_interval)
    log.info("scheduler_loop_exiting")


def _ensure_downstream_item(
    sub: Substrate,
    config: FactoryConfig,
    source_wi,
    handoff: dict,
) -> None:
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
            page_size=100,
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
    if next_type == "implementation":
        iface_ref = custom.get("interface_ref")
        if iface_ref:
            extra["interface_ref"] = iface_ref

    downstream, _ = sub.create_work_item(
        workflow_name=config.workflow_name,
        work_item_type=next_type,
        actor_id="factory-scheduler",
        actor_kind="agent",
        actor_metadata={"role": next_role},
        custom_fields={
            "spec_section": custom.get("spec_section", ""),
            "ac_ids": custom.get("ac_ids", []),
            **extra,
        },
    )

    sub.create_link(
        from_work_item_id=downstream.work_item_id,
        to_work_item_id=source_wi.work_item_id,
        link_type=link_type,
        actor_id="factory-scheduler",
        actor_kind="agent",
    )

    for extra_link_type in additional_links:
        if extra_link_type == "implements":
            interface_ref = custom.get("interface_ref")
            if interface_ref:
                sub.create_link(
                    from_work_item_id=downstream.work_item_id,
                    to_work_item_id=_uuid.UUID(interface_ref),
                    link_type="implements",
                    actor_id="factory-scheduler",
                    actor_kind="agent",
                )

    log.info(
        "handoff_created",
        source_id=str(source_wi.work_item_id),
        source_type=source_wi.work_item_type,
        downstream_id=str(downstream.work_item_id),
        downstream_type=next_type,
    )


def _ref_field_for(next_type: str) -> str | None:
    if next_type == "test_suite":
        return "interface_ref"
    if next_type == "implementation":
        return "test_suite_ref"
    return None


def main() -> None:
    import argparse

    from factory.config import load_config

    parser = argparse.ArgumentParser(description="Software Factory v2 - Scheduler")
    parser.add_argument("--config", type=str, default=None, help="Path to config YAML")
    args = parser.parse_args()
    config = load_config(args.config)
    run_scheduler(config)


if __name__ == "__main__":
    main()
