from __future__ import annotations

import argparse
import signal
import time
from pathlib import Path

import structlog
from substrate import Substrate
from substrate._types import ActorMetadata

from factory.config import FactoryConfig, load_config
from factory.gate import GateResult, evaluate_interface_spec

log = structlog.get_logger()


def run_gate(config: FactoryConfig) -> None:
    sub = Substrate(config.dsn, config.project_name, config.hmac_key_path)
    try:
        gate_loop(sub, config)
    finally:
        sub.close()


def gate_loop(sub: Substrate, config: FactoryConfig) -> None:
    actor_id = "factory-gate-code"
    for role_name in config.gate_roles:
        try:
            sub.register_actor_role(actor_id, role_name)
        except Exception:
            pass
    poll_interval = config.poll_interval_seconds
    shutting_down = False

    def _handle_signal(signum, frame):
        nonlocal shutting_down
        shutting_down = True
        log.info("gate_shutdown_requested", signal=signum)

    signal.signal(signal.SIGTERM, _handle_signal)
    signal.signal(signal.SIGINT, _handle_signal)

    while not shutting_down:
        claimed = False
        page = sub.query_work_items(
            workflow_name=config.workflow_name,
            workflow_version=config.workflow_version,
            current_states=["gating"],
            claimable_now=True,
            page_size=10,
        )
        for wi in page.items:
            claim = sub.acquire_claim(wi.work_item_id, actor_id, config.claim_ttl_seconds)
            log.info(
                "gate_claimed",
                work_item_id=str(wi.work_item_id),
                attempt=claim.attempt_number,
            )
            try:
                process_gate_item(sub, config, wi, actor_id, claim)
                claimed = True
                break
            except Exception:
                log.exception("gate_process_error", work_item_id=str(wi.work_item_id))
                sub.release_claim(wi.work_item_id, actor_id)
        if not claimed and not shutting_down:
            time.sleep(poll_interval)
    log.info("gate_loop_exiting")


def process_gate_item(
    sub: Substrate,
    config: FactoryConfig,
    wi,
    actor_id: str,
    claim,
) -> None:
    work_item_id = wi.work_item_id
    custom = wi.custom_fields or {}
    artifact_path_str = custom.get("artifact_path", "")
    ac_ids_raw = custom.get("ac_ids", [])
    ac_ids = ac_ids_raw if isinstance(ac_ids_raw, list) else [ac_ids_raw]
    artifact_path = Path(artifact_path_str) if artifact_path_str else None

    if artifact_path is None or not artifact_path.exists():
        gate_result = GateResult(
            passed=False,
            gate_name="interface_spec_file_exists",
            diagnostics=[f"Artifact path missing or not found: {artifact_path_str}"],
            artifact_valid=False,
        )
    elif wi.work_item_type == "interface_spec":
        gate_result = evaluate_interface_spec(artifact_path, ac_ids=ac_ids)
    else:
        gate_result = GateResult(
            passed=False,
            gate_name="unknown_type",
            diagnostics=[f"Unknown work_item_type: {wi.work_item_type}"],
        )

    actor_metadata = ActorMetadata(
        role="mechanical_gate",
        channel="code",
        family="code",
        attempt_n=claim.attempt_number,
    ).to_dict()

    if gate_result.passed:
        sub.transition(
            work_item_id,
            "gate_pass",
            actor_id,
            actor_metadata=actor_metadata,
        )
        log.info("gate_passed", work_item_id=str(work_item_id))
    else:
        diagnostics = {
            "gate_name": gate_result.gate_name,
            "passed": gate_result.passed,
            "messages": gate_result.diagnostics,
            "message": "; ".join(gate_result.diagnostics),
        }
        sub.transition(
            work_item_id,
            "gate_fail",
            actor_id,
            actor_metadata=actor_metadata,
            payload={"diagnostics": diagnostics},
            custom_fields={"diagnostics": diagnostics},
        )
        log.info(
            "gate_failed",
            work_item_id=str(work_item_id),
            gate=gate_result.gate_name,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description="Software Factory v2 - Gate process")
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to config YAML",
    )
    args = parser.parse_args()
    config = load_config(args.config)
    run_gate(config)


if __name__ == "__main__":
    main()
