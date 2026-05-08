from __future__ import annotations

import argparse
import signal
import time
from pathlib import Path

import structlog
from substrate import ActorMetadata, Substrate

from factory.config import FactoryConfig, load_config
from factory.context import _to_uuid
from factory.gate import (
    GateResult,
    evaluate_implementation,
    evaluate_interface_spec,
    evaluate_test_suite,
)
from factory.router import route
from factory.runtime import PipelineRuntime

log = structlog.get_logger()


def run_gate(config: FactoryConfig) -> None:
    sub = Substrate(config.dsn, config.project_name, config.hmac_key_path)
    runtime = PipelineRuntime(sub=sub, config=config)
    try:
        gate_loop(runtime)
    finally:
        sub.close()


def gate_loop(runtime: PipelineRuntime) -> None:
    sub = runtime.sub
    config = runtime.config
    actor_id = "factory-gate-code"
    for role_name in config.gate_roles:
        sub.register_actor_role(actor_id, role_name)
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
                process_gate_item(runtime, wi, actor_id, claim)
                claimed = True
                break
            except Exception:
                log.exception("gate_process_error", work_item_id=str(wi.work_item_id))
                sub.release_claim(wi.work_item_id, actor_id)
        if not claimed and not shutting_down:
            time.sleep(poll_interval)
    log.info("gate_loop_exiting")


def _resolve_ref_artifact(sub: Substrate, ref: str) -> Path | None:
    wi = sub.get_work_item(_to_uuid(ref))
    if wi and wi.custom_fields:
        ref_path = wi.custom_fields.get("artifact_path")
        if ref_path:
            return Path(ref_path)
    return None


def process_gate_item(
    runtime: PipelineRuntime,
    wi,
    actor_id: str,
    claim,
) -> None:
    sub = runtime.sub
    config = runtime.config
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
            diagnostic_kind="file_exists",
        )
    elif wi.work_item_type == "interface_spec":
        gate_result = evaluate_interface_spec(artifact_path, ac_ids=ac_ids)
    elif wi.work_item_type == "test_suite":
        interface_ref = custom.get("interface_ref")
        if not interface_ref:
            gate_result = GateResult(
                passed=False,
                gate_name="test_suite_dependency",
                diagnostics=[
                    "Required field 'interface_ref' is missing — "
                    "test_suite cannot be validated without a locked interface_spec"
                ],
                diagnostic_kind="missing_dependency",
            )
        else:
            interface_pyi_path = _resolve_ref_artifact(sub, interface_ref)
            if interface_pyi_path is None:
                gate_result = GateResult(
                    passed=False,
                    gate_name="test_suite_dependency",
                    diagnostics=[
                        f"Referenced interface_spec "
                        f"'{interface_ref}' has no artifact_path — "
                        f"cannot locate locked interface"
                    ],
                    diagnostic_kind="missing_artifact",
                )
            elif not interface_pyi_path.exists():
                gate_result = GateResult(
                    passed=False,
                    gate_name="test_suite_dependency",
                    diagnostics=[
                        f"Referenced interface_spec artifact not found at {interface_pyi_path}"
                    ],
                    diagnostic_kind="missing_artifact",
                )
            else:
                gate_result = evaluate_test_suite(
                    artifact_path,
                    interface_ref_pyi_path=interface_pyi_path,
                )
    elif wi.work_item_type == "implementation":
        interface_ref = custom.get("interface_ref")
        test_suite_ref = custom.get("test_suite_ref")
        if not interface_ref:
            gate_result = GateResult(
                passed=False,
                gate_name="implementation_dependency",
                diagnostics=[
                    "Required field 'interface_ref' is missing — "
                    "implementation cannot be validated without a locked interface_spec"
                ],
                diagnostic_kind="missing_dependency",
            )
        elif not test_suite_ref:
            gate_result = GateResult(
                passed=False,
                gate_name="implementation_dependency",
                diagnostics=[
                    "Required field 'test_suite_ref' is missing — "
                    "implementation cannot be validated without a locked test_suite"
                ],
                diagnostic_kind="missing_dependency",
            )
        else:
            interface_pyi_path = _resolve_ref_artifact(sub, interface_ref)
            test_suite_path = _resolve_ref_artifact(sub, test_suite_ref)
            if interface_pyi_path is None:
                gate_result = GateResult(
                    passed=False,
                    gate_name="implementation_dependency",
                    diagnostics=[
                        f"Referenced interface_spec "
                        f"'{interface_ref}' has no artifact_path — "
                        f"cannot locate locked interface"
                    ],
                    diagnostic_kind="missing_artifact",
                )
            elif not interface_pyi_path.exists():
                gate_result = GateResult(
                    passed=False,
                    gate_name="implementation_dependency",
                    diagnostics=[
                        f"Referenced interface_spec artifact not found at {interface_pyi_path}"
                    ],
                    diagnostic_kind="missing_artifact",
                )
            elif test_suite_path is None:
                gate_result = GateResult(
                    passed=False,
                    gate_name="implementation_dependency",
                    diagnostics=[
                        f"Referenced test_suite "
                        f"'{test_suite_ref}' has no artifact_path — "
                        f"cannot locate test suite"
                    ],
                    diagnostic_kind="missing_artifact",
                )
            elif not test_suite_path.exists():
                gate_result = GateResult(
                    passed=False,
                    gate_name="implementation_dependency",
                    diagnostics=[f"Referenced test_suite artifact not found at {test_suite_path}"],
                    diagnostic_kind="missing_artifact",
                )
            else:
                gate_result = evaluate_implementation(
                    artifact_path,
                    test_suite_path=test_suite_path,
                    interface_pyi_path=interface_pyi_path,
                )
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

    transition_name = "gate_pass" if gate_result.passed else "gate_fail"
    routing = route(
        wi.current_state,
        transition_name,
        gate_result,
        attempt_number=claim.attempt_number,
        attempt_threshold=config.attempt_threshold,
    )
    if gate_result.passed:
        sub.transition(
            work_item_id,
            transition_name,
            actor_id,
            actor_metadata=actor_metadata,
        )
        log.info("gate_passed", work_item_id=str(work_item_id))
    else:
        if routing.target_state == "cannot_proceed":
            transition_name = "gate_escalation"
        diagnostics = routing.custom_fields_update.get("diagnostics", {})
        if not diagnostics:
            diagnostics = {
                "gate_name": gate_result.gate_name,
                "passed": gate_result.passed,
                "messages": gate_result.diagnostics,
                "message": "; ".join(gate_result.diagnostics),
            }
        if gate_result.diagnostic_kind and "diagnostic_kind" not in diagnostics:
            diagnostics["diagnostic_kind"] = gate_result.diagnostic_kind
        sub.transition(
            work_item_id,
            transition_name,
            actor_id,
            actor_metadata=actor_metadata,
            payload={"diagnostics": diagnostics},
            custom_fields={"diagnostics": diagnostics},
        )
        log.info(
            "gate_escalation" if transition_name == "gate_escalation" else "gate_failed",
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
