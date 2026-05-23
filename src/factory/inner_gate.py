from __future__ import annotations

import json
import time
from pathlib import Path

import structlog
from substrate import ActorMetadata, Substrate

from factory.channel import Channel
from factory.config import FactoryConfig, GateTimeouts
from factory.constants import (
    ARTIFACT_FILENAME_CANNOT_PROCEED,
    CUSTOM_FIELD_INTERFACE_REF,
    CUSTOM_FIELD_TEST_SUITE_REF,
    GATE_NAME_INNER_COLLECT,
    GATE_NAME_INNER_IMPORT,
    GATE_NAME_INNER_IMPORT_SYMBOLS,
    GATE_NAME_INNER_JSON_SHAPE,
    GATE_NAME_INNER_MYPY,
    GATE_NAME_INNER_PYTEST,
    GATE_NAME_INNER_RUFF,
    ROLE_INTEGRATOR,
    ROLE_INTERFACE_ARCHITECT,
    ROLE_OUTCOME_VERIFIER,
    ROLE_TEST_AUTHOR,
    TRANSITION_CHANNEL_FAIL,
    TRANSITION_ROUTE_TO_CANNOT_PROCEED,
)
from factory.context import PromptContext, render_prompt
from factory.event_schemas import ChannelFailPayload
from factory.idempotency import make_event_id
from factory.pre_gate import GateScope, PreGateDeps, PreGateResult
from factory.runtime import PipelineRuntime

log = structlog.get_logger()


def _should_failover(invoke_result) -> bool:
    """Determine if a failed invocation warrants immediate fallback channel retry."""
    if invoke_result.success:
        return False
    error = (invoke_result.error_message or "").lower()
    if "empty output" in error:
        return True
    if invoke_result.timed_out:
        return True
    if invoke_result.exit_code not in (None, 0):
        return True
    if "not found in path" in error:
        return True
    return False


def _resolve_pre_gate_deps(sub: Substrate, wi, config: FactoryConfig) -> PreGateDeps:
    from factory.gate_process import _resolve_dependency_refs, _resolve_ref_artifact

    custom = wi.custom_fields or {}
    interface_ref = custom.get(CUSTOM_FIELD_INTERFACE_REF)
    interface_pyi_path = _resolve_ref_artifact(sub, interface_ref) if interface_ref else None
    if interface_ref:
        dep_pyi_paths, dep_spec_paths = _resolve_dependency_refs(
            sub, custom, page_size=config.query_page_size
        )
    else:
        dep_pyi_paths, dep_spec_paths = [], None
    test_suite_ref = custom.get(CUSTOM_FIELD_TEST_SUITE_REF)
    test_suite_path = _resolve_ref_artifact(sub, test_suite_ref) if test_suite_ref else None
    python_executable: str | None = None
    if config.should_use_project_venv():
        from factory.venv import ensure_gate_venv

        python_executable = str(ensure_gate_venv(Path(config.workspace_root)))
    return PreGateDeps(
        interface_pyi_path=interface_pyi_path,
        dep_paths=dep_pyi_paths if dep_pyi_paths else None,
        dep_spec_paths=dep_spec_paths,
        python_executable=python_executable,
        test_suite_path=test_suite_path,
    )


def _build_export_map(
    dep_paths: list[tuple[str, Path]] | None,
) -> dict[str, set[str]]:
    from factory.gate import extract_exports

    export_map: dict[str, set[str]] = {}
    if not dep_paths:
        return export_map
    for module_name, dep_path in dep_paths:
        if dep_path.exists():
            try:
                content = dep_path.read_text()
                export_map[module_name] = extract_exports(content)
            except Exception:
                log.warning(
                    "export_map_extract_failed",
                    module=module_name,
                    path=str(dep_path),
                )
    return export_map


def _handle_invoke_failure(
    sub: Substrate,
    wi,
    ad: Path,
    invoke_result,
    actor_id: str,
    channel: Channel,
    role_name: str,
    attempt_number: int,
    ctx,
    effective_family: str,
    duration_seconds: float | None = None,
    fallback_channel: str | None = None,
    fallback_model: str | None = None,
) -> None:
    work_item_id = wi.work_item_id
    if invoke_result.error_message == "cannot_proceed":
        cp_path = ad / ARTIFACT_FILENAME_CANNOT_PROCEED
        if cp_path.exists():
            cp_data = cp_path.read_bytes()
            sub.transition(
                work_item_id,
                TRANSITION_ROUTE_TO_CANNOT_PROCEED,
                actor_id,
                actor_metadata=ActorMetadata(
                    role=role_name,
                    channel=channel.name,
                    family=effective_family,
                    attempt_n=attempt_number,
                    context_hash=ctx.context_hash,
                    prompt_template_hash=ctx.prompt_template_hash,
                ).to_dict(),
                custom_fields={
                    "diagnostics": json.loads(cp_data),
                },
                event_id=make_event_id(
                    work_item_id,
                    TRANSITION_ROUTE_TO_CANNOT_PROCEED,
                    attempt_number,
                    extra="cannot_proceed",
                ),
            )
        else:
            diag_base = {
                "error_message": "cannot_proceed without diagnostics file",
                "duration_seconds": duration_seconds,
            }
            if fallback_channel:
                diag_base["fallback_channel"] = fallback_channel
                diag_base["fallback_model"] = fallback_model
            sub.transition(
                work_item_id,
                TRANSITION_CHANNEL_FAIL,
                actor_id,
                actor_metadata=ActorMetadata(
                    role=role_name,
                    channel=channel.name,
                    family=effective_family,
                    attempt_n=attempt_number,
                    context_hash=ctx.context_hash,
                    prompt_template_hash=ctx.prompt_template_hash,
                ).to_dict(),
                payload=ChannelFailPayload(diagnostics=diag_base).to_dict(),
                event_id=make_event_id(
                    work_item_id, TRANSITION_CHANNEL_FAIL, attempt_number, extra="cannot_proceed"
                ),
            )
        return
    log.error(
        "channel_invoke_failed",
        work_item_id=str(work_item_id),
        error=invoke_result.error_message,
    )
    diag = {
        "error_message": invoke_result.error_message,
        "timed_out": invoke_result.timed_out,
        "exit_code": invoke_result.exit_code,
        "duration_seconds": duration_seconds,
    }
    if fallback_channel:
        diag["fallback_channel"] = fallback_channel
        diag["fallback_model"] = fallback_model
    sub.transition(
        work_item_id,
        TRANSITION_CHANNEL_FAIL,
        actor_id,
        actor_metadata=ActorMetadata(
            role=role_name,
            channel=channel.name,
            family=effective_family,
            attempt_n=attempt_number,
            context_hash=ctx.context_hash,
            prompt_template_hash=ctx.prompt_template_hash,
        ).to_dict(),
        payload=ChannelFailPayload(diagnostics=diag).to_dict(),
        event_id=make_event_id(
            work_item_id, TRANSITION_CHANNEL_FAIL, attempt_number, extra="invoke_failure"
        ),
    )


def _inner_gate_label(pre_result: PreGateResult, role_name: str) -> str:
    if role_name in (ROLE_INTEGRATOR, ROLE_OUTCOME_VERIFIER):
        return GATE_NAME_INNER_JSON_SHAPE
    if not pre_result.imports_symbols_passed:
        return GATE_NAME_INNER_IMPORT_SYMBOLS
    if not pre_result.mypy_passed:
        return GATE_NAME_INNER_MYPY
    if not pre_result.ruff_passed:
        return GATE_NAME_INNER_RUFF
    if not pre_result.pytest_passed:
        if role_name == ROLE_INTERFACE_ARCHITECT:
            return GATE_NAME_INNER_IMPORT
        if role_name == ROLE_TEST_AUTHOR:
            return GATE_NAME_INNER_COLLECT
        return GATE_NAME_INNER_PYTEST
    return GATE_NAME_INNER_PYTEST


def _run_pre_gate(
    role_name: str,
    artifact_path: Path,
    deps: PreGateDeps,
    config: FactoryConfig | None = None,
    export_map: dict[str, set[str]] | None = None,
) -> PreGateResult:
    from factory.pre_gate import (
        pre_gate_implementation,
        pre_gate_integrator,
        pre_gate_interface_spec,
        pre_gate_outcome_verifier,
        pre_gate_test_suite,
    )

    t = config.gate_timeouts if config else GateTimeouts()
    gate_scope = GateScope()
    if role_name == ROLE_INTERFACE_ARCHITECT:
        req_path = config.workspace_root / "requirements.txt" if config else None
        return pre_gate_interface_spec(
            artifact_path,
            dependency_pyi_paths=deps.dep_paths,
            python_executable=deps.python_executable,
            timeouts=t,
            requirements_path=req_path if req_path and req_path.exists() else None,
        )
    if role_name == ROLE_TEST_AUTHOR:
        return pre_gate_test_suite(
            artifact_path,
            interface_pyi_path=deps.interface_pyi_path,
            dependency_pyi_paths=deps.dep_paths,
            dependency_spec_paths=deps.dep_spec_paths,
            python_executable=deps.python_executable,
            timeouts=t,
            export_map=export_map,
            gate_scope=gate_scope,
        )
    if role_name == ROLE_INTEGRATOR:
        return pre_gate_integrator(artifact_path)
    if role_name == ROLE_OUTCOME_VERIFIER:
        return pre_gate_outcome_verifier(artifact_path)
    return pre_gate_implementation(
        artifact_path,
        interface_pyi_path=deps.interface_pyi_path,
        dependency_pyi_paths=deps.dep_paths,
        dependency_spec_paths=deps.dep_spec_paths,
        python_executable=deps.python_executable,
        test_suite_path=deps.test_suite_path,
        timeouts=t,
        export_map=export_map,
        gate_scope=gate_scope,
    )


def _inner_gate_loop(
    runtime: PipelineRuntime,
    wi,
    actor_id: str,
    claim,
    role_name: str,
    channel: Channel,
    ctx: PromptContext,
    artifact_path: Path,
    attempt_number: int,
    ad: Path,
    timeout: int,
    invocation_start: float,
    effective_family: str,
    config: FactoryConfig,
    extra_env: dict[str, str] | None = None,
) -> tuple[Path | None, PromptContext, float, list[dict]]:
    from factory.failure_summary import FailureEntry

    sub = runtime.sub
    work_item_id = str(wi.work_item_id)
    pre_gate_deps = _resolve_pre_gate_deps(sub, wi, config)
    export_map = _build_export_map(pre_gate_deps.dep_paths)
    max_retries = config.inner_gate_retries
    current_artifact = artifact_path
    current_ctx = ctx
    duration_seconds = round(time.monotonic() - invocation_start, 3)
    inner_gate_attempts: list[dict] = []

    for retry in range(max_retries):
        if not current_artifact.exists():
            log.warning("inner_gate_artifact_missing", work_item_id=work_item_id)
            return current_artifact, current_ctx, duration_seconds, inner_gate_attempts

        pre_result = _run_pre_gate(
            role_name,
            current_artifact,
            pre_gate_deps,
            config,
            export_map=export_map,
        )

        gate_label = _inner_gate_label(pre_result, role_name)

        inner_gate_attempts.append(
            {
                "retry": retry,
                "gate_name": gate_label,
                "passed": pre_result.passed,
                "diagnostics": pre_result.diagnostics[:5],
            }
        )

        if pre_result.passed:
            log.info(
                "inner_gate_passed",
                work_item_id=work_item_id,
                retry=retry,
                inner_gate_name=gate_label,
                import_feedback_kind=pre_result.import_feedback_kind,
            )
            return current_artifact, current_ctx, duration_seconds, inner_gate_attempts

        log.info(
            "inner_gate_failed_retry",
            work_item_id=work_item_id,
            retry=retry,
            inner_gate_name=gate_label,
            imports_symbols_passed=pre_result.imports_symbols_passed,
            mypy_passed=pre_result.mypy_passed,
            ruff_passed=pre_result.ruff_passed,
            pytest_passed=pre_result.pytest_passed,
            diagnostics=pre_result.diagnostics[:3],
            import_feedback_kind=pre_result.import_feedback_kind,
        )

        max_feedback = config.inner_gate_max_feedback_chars
        truncated_output = pre_result.output[-max_feedback:] if pre_result.output else ""

        retry_failures = [
            *current_ctx.prior_failures,
            FailureEntry(
                attempt_number=attempt_number,
                role=role_name,
                channel=channel.name,
                gate_name=gate_label,
                diagnostic="; ".join(pre_result.diagnostics[:5]),
                gate_output=truncated_output,
            ),
        ]
        import_feedback = pre_result.import_feedback or current_ctx.import_feedback
        current_ctx = PromptContext(
            work_item_id=current_ctx.work_item_id,
            role=current_ctx.role,
            spec_section=current_ctx.spec_section,
            ac_ids=current_ctx.ac_ids,
            glossary=current_ctx.glossary,
            prior_failures=retry_failures,
            prompt_template=current_ctx.prompt_template,
            context_hash=current_ctx.context_hash,
            prompt_template_hash=current_ctx.prompt_template_hash,
            extra_artifacts=current_ctx.extra_artifacts,
            stub_only_deps=current_ctx.stub_only_deps,
            export_map=current_ctx.export_map,
            import_feedback=import_feedback,
        )
        retry_prompt = render_prompt(current_ctx)
        retry_ad = ad / f"retry-{retry}"
        retry_ad.mkdir(parents=True, exist_ok=True)
        retry_start = time.monotonic()
        retry_result = channel.invoke(
            role_name, retry_prompt, retry_ad, timeout, extra_env=extra_env
        )
        duration_seconds += round(time.monotonic() - retry_start, 3)
        retry_fb_channel = None
        retry_fb_model = None

        if not retry_result.success and _should_failover(retry_result):
            fb_channel = runtime.fallback_channel_for_role(role_name)
            role_config = config.get_role_config(role_name)
            if fb_channel is not None:
                retry_fb_channel = fb_channel.name
                retry_fb_model = role_config.fallback_model if role_config else None
                log.info(
                    "inner_gate_failover_attempt",
                    work_item_id=work_item_id,
                    retry=retry,
                    primary=channel.name,
                    fallback=retry_fb_channel,
                )
                fb_start = time.monotonic()
                retry_result = fb_channel.invoke(
                    role_name,
                    retry_prompt,
                    retry_ad,
                    timeout,
                    extra_env=extra_env,
                    model_override=retry_fb_model,
                )
                duration_seconds += round(time.monotonic() - fb_start, 3)
                if retry_result.success:
                    effective_family = retry_result.family or fb_channel.family
                else:
                    log.warning(
                        "inner_gate_failover_failed",
                        work_item_id=work_item_id,
                        retry=retry,
                        primary=channel.name,
                        fallback=retry_fb_channel,
                        error=retry_result.error_message,
                    )

        if not retry_result.success:
            _handle_invoke_failure(
                sub,
                wi,
                retry_ad,
                retry_result,
                actor_id,
                channel,
                role_name,
                attempt_number,
                current_ctx,
                effective_family,
                duration_seconds,
                fallback_channel=retry_fb_channel,
                fallback_model=retry_fb_model,
            )
            return None, current_ctx, duration_seconds, inner_gate_attempts
        current_artifact = retry_ad / retry_result.artifact_name

    log.info(
        "inner_gate_exhausted_retries",
        work_item_id=work_item_id,
        max_retries=max_retries,
    )
    return current_artifact, current_ctx, duration_seconds, inner_gate_attempts
