from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import structlog
from substrate import ActorMetadata, Substrate

from factory.channel import Channel
from factory.config import FactoryConfig, GateTimeouts, load_config
from factory.constants import (
    ARTIFACT_FILENAME_CANNOT_PROCEED,
    ARTIFACT_FILENAME_JURY_VERDICT,
    CHANNEL_CLAUDE_CODE,
    CHANNEL_CODE,
    CHANNEL_GEMINI_CLI,
    CHANNEL_OPENCODE,
    CUSTOM_FIELD_ARTIFACT_HASH,
    CUSTOM_FIELD_ARTIFACT_PATH,
    CUSTOM_FIELD_INTERFACE_REF,
    CUSTOM_FIELD_TEST_SUITE_REF,
    GATE_NAME_INNER_COLLECT,
    GATE_NAME_INNER_IMPORT,
    GATE_NAME_INNER_IMPORT_SYMBOLS,
    GATE_NAME_INNER_MYPY,
    GATE_NAME_INNER_PYTEST,
    GATE_NAME_INNER_RUFF,
    MAX_ARTIFACT_SIZE_BYTES,
    ROLE_CROSS_FAMILY_REVIEWER,
    ROLE_FRONTIER_JUDGE,
    ROLE_IMPLEMENTER,
    ROLE_INTEGRATOR,
    ROLE_INTERFACE_ARCHITECT,
    ROLE_OUTCOME_VERIFIER,
    ROLE_TEST_AUTHOR,
    STATE_NEW,
    TRANSITION_CHANNEL_FAIL,
    TRANSITION_CLAIM,
    TRANSITION_GATE_FAIL,
    TRANSITION_ROUTE_TO_CANNOT_PROCEED,
    TRANSITION_SUBMIT,
)
from factory.context import (
    PromptContext,
    derive_context,
    derive_implementer_context,
    derive_integrator_context,
    derive_jury_context,
    derive_outcome_verifier_context,
    derive_review_context,
    derive_test_author_context,
    render_prompt,
)
from factory.event_schemas import ChannelFailPayload, SubmitPayload
from factory.pre_gate import GateScope, PreGateDeps, PreGateResult
from factory.runtime import PipelineRuntime
from factory.workspace import (
    ArtifactManifest,
    attempt_dir,
    compute_sha256,
    find_resumable_artifact,
    write_artifact,
)

log = structlog.get_logger()

_INNER_GATE_ROLES = frozenset(
    {
        ROLE_INTERFACE_ARCHITECT,
        ROLE_TEST_AUTHOR,
        ROLE_IMPLEMENTER,
        ROLE_INTEGRATOR,
        ROLE_OUTCOME_VERIFIER,
    }
)


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


def _role_for_type(work_item_type: str, config: FactoryConfig) -> str | None:
    for type_name, role_name in config.type_to_role:
        if type_name == work_item_type:
            return role_name
    return None


def _derive_role_context(
    runtime: PipelineRuntime,
    work_item_id: str,
    role_name: str,
):
    spec = runtime.spec_content
    if role_name == ROLE_TEST_AUTHOR:
        return derive_test_author_context(runtime.sub, work_item_id, spec_content=spec)
    if role_name == ROLE_IMPLEMENTER:
        return derive_implementer_context(runtime.sub, work_item_id, spec_content=spec)
    if role_name == ROLE_CROSS_FAMILY_REVIEWER:
        return derive_review_context(runtime.sub, work_item_id, spec_content=spec)
    if role_name == ROLE_FRONTIER_JUDGE:
        return derive_jury_context(runtime.sub, work_item_id, spec_content=spec)
    if role_name == ROLE_INTEGRATOR:
        return derive_integrator_context(runtime.sub, work_item_id, spec_content=spec)
    if role_name == ROLE_OUTCOME_VERIFIER:
        return derive_outcome_verifier_context(runtime.sub, work_item_id, spec_content=spec)
    return derive_context(runtime.sub, work_item_id, role_name, spec_content=spec)


def run_worker(
    config: FactoryConfig,
    channel: Channel | None = None,
    channels: dict[str, Channel] | None = None,
) -> None:
    sub = Substrate(config.dsn, config.project_name, config.hmac_key_path)
    spec_content = _load_spec(config)
    runtime = PipelineRuntime(
        sub=sub,
        config=config,
        spec_content=spec_content,
        channel=channel,
        channels=channels,
    )
    try:
        worker_loop(runtime)
    finally:
        sub.close()


def _load_spec(config: FactoryConfig) -> str | None:
    if config.spec_file is not None and config.spec_file.exists():
        return config.spec_file.read_text()
    return None


def worker_loop(runtime: PipelineRuntime) -> None:
    sub = runtime.sub
    config = runtime.config
    first_role = config.worker_roles[0] if config.worker_roles else ""
    default_channel = runtime.channel_for_role(first_role)
    actor_id = config.worker_actor_id(default_channel.name)
    for role_name in config.worker_roles:
        sub.register_actor_role(actor_id, role_name)
    poll_interval = config.poll_interval_seconds
    max_attempts = config.channel_backoff_max_attempts
    backoff_base = config.channel_backoff_base_seconds
    shutting_down = False
    channel_consecutive_failures: dict[str, int] = {}
    channel_backoff_until: dict[str, float] = {}

    def _handle_signal(signum, frame):
        nonlocal shutting_down
        shutting_down = True
        log.info("shutdown_requested", signal=signum)

    import signal as signal_mod

    signal_mod.signal(signal_mod.SIGTERM, _handle_signal)
    signal_mod.signal(signal_mod.SIGINT, _handle_signal)

    while not shutting_down:
        claimed = False
        page = sub.query_work_items(
            workflow_name=config.workflow_name,
            workflow_version=config.workflow_version,
            current_states=[STATE_NEW],
            claimable_now=True,
            page_size=config.query_page_size,
        )
        for wi in page.items:
            role_name = _role_for_type(wi.work_item_type, config)
            if role_name is None:
                continue
            channel = runtime.channel_for_role(role_name)
            backoff = channel_consecutive_failures.get(channel.name, 0)
            if backoff >= max_attempts:
                now = time.monotonic()
                deadline = channel_backoff_until.get(channel.name, 0)
                if now < deadline:
                    log.warning(
                        "channel_backoff",
                        channel=channel.name,
                        consecutive_failures=backoff,
                        remaining_seconds=round(deadline - now, 1),
                    )
                    continue
                log.info(
                    "channel_backoff_probe",
                    channel=channel.name,
                    consecutive_failures=backoff,
                    message="Cooldown elapsed, probing one item",
                )
            claim = sub.acquire_claim(wi.work_item_id, actor_id, config.claim_ttl_seconds)
            if claim.attempt_number >= config.attempt_threshold:
                log.warning(
                    "claim_near_budget",
                    work_item_id=str(wi.work_item_id),
                    attempt=claim.attempt_number,
                    threshold=config.attempt_threshold,
                )
                sub.transition(
                    wi.work_item_id,
                    TRANSITION_CLAIM,
                    actor_id,
                    actor_metadata=ActorMetadata(
                        role=role_name,
                        channel=channel.name,
                    ).to_dict(),
                )
                sub.transition(
                    wi.work_item_id,
                    TRANSITION_ROUTE_TO_CANNOT_PROCEED,
                    actor_id,
                    actor_metadata=ActorMetadata(
                        role=role_name,
                        channel=channel.name,
                    ).to_dict(),
                    custom_fields={
                        "diagnostics": {
                            "message": (
                                f"Escalated to cannot_proceed after {claim.attempt_number} "
                                f"attempts (threshold={config.attempt_threshold})"
                            ),
                            "diagnostic_kind": "cannot_proceed_seam",
                        }
                    },
                )
                continue
            sub.transition(
                wi.work_item_id,
                TRANSITION_CLAIM,
                actor_id,
                actor_metadata=ActorMetadata(
                    role=role_name,
                    channel=channel.name,
                    family=channel.family,
                    attempt_n=claim.attempt_number,
                ).to_dict(),
            )
            log.info(
                "claim_acquired",
                work_item_id=str(wi.work_item_id),
                attempt=claim.attempt_number,
            )
            try:
                process_work_item(runtime, wi, actor_id, claim, role_name)
                claimed = True
                channel_consecutive_failures.pop(channel.name, None)
                channel_backoff_until.pop(channel.name, None)
            except Exception:
                log.exception("process_error", work_item_id=str(wi.work_item_id))
                sub.release_claim(wi.work_item_id, actor_id)
                prev = channel_consecutive_failures.get(channel.name, 0)
                new_count = prev + 1
                channel_consecutive_failures[channel.name] = new_count
                if new_count >= max_attempts:
                    backoff_seconds = min(
                        backoff_base * (2 ** (new_count - max_attempts)),
                        300,
                    )
                    channel_backoff_until[channel.name] = time.monotonic() + backoff_seconds
                    log.warning(
                        "channel_backoff_set",
                        channel=channel.name,
                        consecutive_failures=new_count,
                        backoff_seconds=backoff_seconds,
                    )
            break
        if not claimed and not shutting_down:
            time.sleep(poll_interval)
    log.info("worker_loop_exiting")


def _has_prior_gate_fail(sub: Substrate, work_item_id: str) -> bool:
    events = sub.read_events(work_item_id=work_item_id)
    return any(e.transition in (TRANSITION_GATE_FAIL, TRANSITION_CHANNEL_FAIL) for e in events)


def _resolve_extra_env(config: FactoryConfig, role_name: str) -> dict[str, str] | None:
    role_config = config.get_role_config(role_name)
    if not role_config or not role_config.provider:
        return None
    from factory.credentials import inject_credentials_into_env, load_credentials

    credentials = load_credentials(config.credentials_path)
    if not credentials:
        return None
    return inject_credentials_into_env(credentials, role_config.provider)


def _resolve_pre_gate_deps(sub: Substrate, wi, config: FactoryConfig) -> PreGateDeps:
    from factory.gate_process import _resolve_dependency_refs, _resolve_ref_artifact

    custom = wi.custom_fields or {}
    interface_ref = custom.get(CUSTOM_FIELD_INTERFACE_REF)
    interface_pyi_path = _resolve_ref_artifact(sub, interface_ref) if interface_ref else None
    if interface_ref:
        dep_pyi_paths, dep_spec_paths = _resolve_dependency_refs(sub, custom)
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


def process_work_item(
    runtime: PipelineRuntime,
    wi,
    actor_id: str,
    claim,
    role_name: str,
) -> None:
    sub = runtime.sub
    config = runtime.config
    channel = runtime.channel_for_role(role_name)
    work_item_id = str(wi.work_item_id)
    attempt_number = claim.attempt_number
    wr = runtime.workspace_root
    if not _has_prior_gate_fail(sub, work_item_id):
        resumable = find_resumable_artifact(wr, work_item_id)
        if resumable is not None:
            log.info(
                "resuming_from_artifact",
                work_item_id=work_item_id,
                attempt=resumable[0],
            )
            resumable_artifact_path = (
                attempt_dir(wr, work_item_id, resumable[0]) / resumable[1].artifact_name
            )
            _resume_and_submit(
                sub,
                wi,
                resumable[0],
                resumable[1],
                actor_id,
                channel,
                resumable_artifact_path,
                role_name=role_name,
            )
            return
    else:
        log.info(
            "skipping_resume_due_to_prior_gate_fail",
            work_item_id=work_item_id,
        )

    ctx = _derive_role_context(runtime, wi.work_item_id, role_name)
    role_config = config.get_role_config(role_name)
    timeout = role_config.timeout_seconds if role_config else config.claim_ttl_seconds
    ad = attempt_dir(wr, work_item_id, attempt_number)
    extra_env = _resolve_extra_env(config, role_name)

    if role_name == ROLE_FRONTIER_JUDGE:
        _process_jury_work_item(
            runtime,
            wi,
            actor_id,
            claim,
            ctx,
            ad,
            timeout,
            extra_env,
        )
        return

    channel = runtime.channel_for_role(role_name)
    if config.per_channel_timeout and channel.name in config.per_channel_timeout:
        timeout = config.per_channel_timeout[channel.name]
    prompt = render_prompt(ctx)
    invocation_start = time.monotonic()
    invoke_result = channel.invoke(role_name, prompt, ad, timeout, extra_env=extra_env)
    invocation_end = time.monotonic()
    duration_seconds = round(invocation_end - invocation_start, 3)
    effective_family = invoke_result.family or channel.family
    fallback_channel = None
    fallback_model = None

    if not invoke_result.success and _should_failover(invoke_result):
        fb_channel = runtime.fallback_channel_for_role(role_name)
        role_config = config.get_role_config(role_name)
        if fb_channel is not None:
            fallback_channel = fb_channel.name
            fallback_model = role_config.fallback_model if role_config else None
            log.info(
                "channel_failover_attempt",
                work_item_id=work_item_id,
                primary=channel.name,
                fallback=fallback_channel,
            )
            fb_start = time.monotonic()
            invoke_result = fb_channel.invoke(
                role_name,
                prompt,
                ad,
                timeout,
                extra_env=extra_env,
                model_override=fallback_model,
            )
            duration_seconds += round(time.monotonic() - fb_start, 3)
            if invoke_result.success:
                effective_family = invoke_result.family or fb_channel.family
            else:
                log.warning(
                    "channel_failover_failed",
                    work_item_id=work_item_id,
                    primary=channel.name,
                    fallback=fallback_channel,
                    error=invoke_result.error_message,
                )

    if not invoke_result.success:
        _handle_invoke_failure(
            sub,
            wi,
            ad,
            invoke_result,
            actor_id,
            channel,
            role_name,
            attempt_number,
            ctx,
            effective_family,
            duration_seconds,
            fallback_channel=fallback_channel,
            fallback_model=fallback_model,
        )
        return

    artifact_path = ad / invoke_result.artifact_name

    inner_gate_attempts: list[dict] | None = None
    if role_name in _INNER_GATE_ROLES and config.inner_gate_retries > 0:
        artifact_path, ctx, duration_seconds, inner_gate_attempts = _inner_gate_loop(
            runtime,
            wi,
            actor_id,
            claim,
            role_name,
            channel,
            ctx,
            artifact_path,
            attempt_number,
            ad,
            timeout,
            invocation_start,
            effective_family,
            config,
            extra_env=extra_env,
        )
        if artifact_path is None:
            return

    artifact_stat = artifact_path.stat()
    if artifact_stat.st_size > MAX_ARTIFACT_SIZE_BYTES:
        log.error(
            "artifact_oversized",
            work_item_id=work_item_id,
            path=str(artifact_path),
            size=artifact_stat.st_size,
            limit=MAX_ARTIFACT_SIZE_BYTES,
        )
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
            payload=ChannelFailPayload(
                diagnostics={
                    "error_message": (
                        f"Artifact size {artifact_stat.st_size} bytes exceeds "
                        f"limit {MAX_ARTIFACT_SIZE_BYTES} bytes"
                    ),
                    "duration_seconds": duration_seconds,
                }
            ).to_dict(),
        )
        return

    artifact_data = artifact_path.read_bytes()
    sha = compute_sha256(artifact_data)
    manifest = ArtifactManifest(
        attempt_number=attempt_number,
        work_item_id=work_item_id,
        artifact_name=invoke_result.artifact_name,
        artifact_sha256=sha,
        artifact_size=len(artifact_data),
        actor_id=actor_id,
        channel=channel.name,
        family=effective_family,
        model=None,
        context_hash=ctx.context_hash,
    )
    write_artifact(ad, invoke_result.artifact_name, artifact_data, manifest)
    actor_metadata = ActorMetadata(
        role=role_name,
        channel=channel.name,
        family=effective_family,
        attempt_n=attempt_number,
        context_hash=ctx.context_hash,
        prompt_template_hash=ctx.prompt_template_hash,
    ).to_dict()
    sub.transition(
        wi.work_item_id,
        TRANSITION_SUBMIT,
        actor_id,
        actor_metadata=actor_metadata,
        payload=SubmitPayload(
            duration_seconds=duration_seconds,
            inner_gate_attempts=inner_gate_attempts,
        ).to_dict(),
        custom_fields={
            CUSTOM_FIELD_ARTIFACT_PATH: str(artifact_path),
            CUSTOM_FIELD_ARTIFACT_HASH: sha,
        },
    )


def _inner_gate_label(pre_result: PreGateResult, role_name: str) -> str:
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
        pre_gate_interface_spec,
        pre_gate_test_suite,
    )

    t = config.gate_timeouts if config else GateTimeouts()
    gate_scope = GateScope()
    if role_name == ROLE_INTERFACE_ARCHITECT:
        return pre_gate_interface_spec(
            artifact_path,
            dependency_pyi_paths=deps.dep_paths,
            python_executable=deps.python_executable,
            timeouts=t,
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

        from factory.failure_summary import FailureEntry

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
    )


def _resume_and_submit(
    sub: Substrate,
    wi,
    resumable_attempt: int,
    manifest: ArtifactManifest,
    actor_id: str,
    channel: Channel,
    artifact_path: Path,
    role_name: str,
) -> None:
    actor_metadata = ActorMetadata(
        role=role_name,
        channel=manifest.channel or channel.name,
        family=manifest.family or channel.family,
        attempt_n=resumable_attempt,
        context_hash=manifest.context_hash,
        prompt_template_hash=None,
    ).to_dict()
    sub.transition(
        wi.work_item_id,
        TRANSITION_SUBMIT,
        actor_id,
        actor_metadata=actor_metadata,
        custom_fields={
            CUSTOM_FIELD_ARTIFACT_PATH: str(artifact_path),
            CUSTOM_FIELD_ARTIFACT_HASH: manifest.artifact_sha256,
        },
    )


def _resolve_jury_channels(
    runtime: PipelineRuntime,
    config: FactoryConfig,
) -> tuple[
    dict[str, Channel],
    dict[str, str | None],
    dict[str, Channel | None],
    dict[str, str | None],
]:
    """Build a dict of juror channels and models from config, including fallbacks."""
    jury_channels: dict[str, Channel] = {}
    jury_models: dict[str, str | None] = {}
    jury_fallback_channels: dict[str, Channel | None] = {}
    jury_fallback_models: dict[str, str | None] = {}
    for rc in config.roles:
        if rc.role == ROLE_FRONTIER_JUDGE:
            ch = runtime.channels.get(rc.channel) if runtime.channels else runtime.channel
            if ch is not None:
                model_id = rc.model.split("/")[-1] if rc.model else "default"
                key = f"{rc.channel}-{model_id}"
                jury_channels[key] = ch
                jury_models[key] = rc.model
                fb_ch = None
                if rc.fallback_channel:
                    fb_ch = runtime.channels.get(rc.fallback_channel) if runtime.channels else None
                    if (
                        fb_ch is None
                        and runtime.channel
                        and runtime.channel.name == rc.fallback_channel
                    ):
                        fb_ch = runtime.channel
                jury_fallback_channels[key] = fb_ch
                jury_fallback_models[key] = rc.fallback_model
    return jury_channels, jury_models, jury_fallback_channels, jury_fallback_models


def _process_jury_work_item(
    runtime: PipelineRuntime,
    wi,
    actor_id: str,
    claim,
    ctx: PromptContext,
    ad: Path,
    timeout: int,
    extra_env: dict[str, str] | None,
) -> None:
    from factory.jury import run_jury

    sub = runtime.sub
    config = runtime.config
    work_item_id = str(wi.work_item_id)
    attempt_number = claim.attempt_number
    (
        jury_channels,
        jury_models,
        jury_fallback_channels,
        jury_fallback_models,
    ) = _resolve_jury_channels(runtime, config)
    if not jury_channels:
        log.error("no_jury_channels_configured", work_item_id=work_item_id)
        sub.transition(
            wi.work_item_id,
            TRANSITION_CHANNEL_FAIL,
            actor_id,
            actor_metadata=ActorMetadata(
                role=ROLE_FRONTIER_JUDGE,
                channel="none",
                family="",
                attempt_n=attempt_number,
                context_hash=ctx.context_hash,
                prompt_template_hash=ctx.prompt_template_hash,
            ).to_dict(),
            payload=ChannelFailPayload(
                diagnostics={
                    "error_message": "No jury channels configured for frontier_judge role",
                }
            ).to_dict(),
        )
        return

    prompt = render_prompt(ctx)
    try:
        verdict = run_jury(
            channels=jury_channels,
            prompt=prompt,
            outputs_dir=ad,
            timeout=timeout,
            quorum=getattr(config, "jury_quorum", 2),
            models=jury_models,
            fallback_channels=jury_fallback_channels,
            fallback_models=jury_fallback_models,
        )
    except Exception:
        log.exception("jury_invoke_failed", work_item_id=work_item_id)
        sub.transition(
            wi.work_item_id,
            TRANSITION_CHANNEL_FAIL,
            actor_id,
            actor_metadata=ActorMetadata(
                role=ROLE_FRONTIER_JUDGE,
                channel="jury_aggregate",
                family="multi",
                attempt_n=attempt_number,
                context_hash=ctx.context_hash,
                prompt_template_hash=ctx.prompt_template_hash,
            ).to_dict(),
            payload=ChannelFailPayload(
                diagnostics={
                    "error_message": "jury invocation raised an exception",
                    "duration_seconds": 0,
                }
            ).to_dict(),
        )
        return
    verdict_path = ad / ARTIFACT_FILENAME_JURY_VERDICT
    verdict_path.write_text(
        json.dumps(
            {
                "passed": verdict.passed,
                "votes_for": verdict.votes_for,
                "votes_against": verdict.votes_against,
                "quorum_met": verdict.quorum_met,
                "disagreement_rationale": verdict.disagreement_rationale,
                "verdicts": [
                    {
                        "passed": v.passed,
                        "rationale": v.rationale,
                        "channel": v.channel,
                        "family": v.family,
                    }
                    for v in verdict.verdicts
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    artifact_data = verdict_path.read_bytes()
    sha = compute_sha256(artifact_data)
    manifest = ArtifactManifest(
        attempt_number=attempt_number,
        work_item_id=work_item_id,
        artifact_name=ARTIFACT_FILENAME_JURY_VERDICT,
        artifact_sha256=sha,
        artifact_size=len(artifact_data),
        actor_id=actor_id,
        channel="jury_aggregate",
        family="multi",
        model=None,
        context_hash=ctx.context_hash,
    )
    write_artifact(ad, ARTIFACT_FILENAME_JURY_VERDICT, artifact_data, manifest)
    actor_metadata = ActorMetadata(
        role=ROLE_FRONTIER_JUDGE,
        channel="jury_aggregate",
        family="multi",
        attempt_n=attempt_number,
        context_hash=ctx.context_hash,
        prompt_template_hash=ctx.prompt_template_hash,
    ).to_dict()
    sub.transition(
        wi.work_item_id,
        TRANSITION_SUBMIT,
        actor_id,
        actor_metadata=actor_metadata,
        custom_fields={
            CUSTOM_FIELD_ARTIFACT_PATH: str(verdict_path),
            CUSTOM_FIELD_ARTIFACT_HASH: sha,
        },
    )


_CHANNEL_CONSTRUCTORS: dict[str, type[Channel]] = {}


def _register_channel(channel_name: str, import_path: str, class_name: str) -> None:
    import importlib

    _CHANNEL_CONSTRUCTORS[channel_name] = getattr(importlib.import_module(import_path), class_name)


_register_channel(CHANNEL_OPENCODE, "factory.opencode_channel", "OpenCodeChannel")
_register_channel(CHANNEL_CLAUDE_CODE, "factory.claude_code_channel", "ClaudeCodeChannel")
_register_channel(CHANNEL_GEMINI_CLI, "factory.gemini_channel", "GeminiCLIChannel")

_SUPPORTED_CHANNEL_NAMES = ", ".join(sorted(_CHANNEL_CONSTRUCTORS))


def _create_channels(config: FactoryConfig) -> dict[str, Channel]:
    channel_names = set(rc.channel for rc in config.roles if rc.channel != CHANNEL_CODE)
    channels: dict[str, Channel] = {}
    for ch_name in channel_names:
        constructor = _CHANNEL_CONSTRUCTORS.get(ch_name)
        if constructor is None:
            raise ValueError(f"Unknown channel: {ch_name}. Supported: {_SUPPORTED_CHANNEL_NAMES}")
        channels[ch_name] = constructor(config)
    if not channels:
        raise ValueError("No model channels configured")
    return channels


def _create_channel(config: FactoryConfig) -> Channel:
    channels = _create_channels(config)
    if len(channels) == 1:
        return next(iter(channels.values()))
    raise NotImplementedError("Multi-channel dispatch requires run_worker with channels dict")


def _main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Software Factory v2 - Worker process")
    parser.add_argument(
        "--config",
        type=str,
        default=None,
        help="Path to factory config YAML",
    )
    args = parser.parse_args(argv)
    config = load_config(args.config)
    channels = _create_channels(config)
    run_worker(config, channels=channels)


def main() -> None:
    _main()


if __name__ == "__main__":
    main()
