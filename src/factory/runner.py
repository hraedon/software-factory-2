from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import structlog
from substrate import ActorMetadata, Substrate

from factory.channel import Channel
from factory.config import FactoryConfig, load_config
from factory.constants import (
    ARTIFACT_FILENAME_CANNOT_PROCEED,
    CHANNEL_CLAUDE_CODE,
    CHANNEL_CODE,
    CHANNEL_OPENCODE,
    CUSTOM_FIELD_ARTIFACT_HASH,
    CUSTOM_FIELD_ARTIFACT_PATH,
    CUSTOM_FIELD_INTERFACE_REF,
    CUSTOM_FIELD_TEST_SUITE_REF,
    ROLE_IMPLEMENTER,
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
    derive_test_author_context,
    render_prompt,
)
from factory.event_schemas import ChannelFailPayload, SubmitPayload
from factory.pre_gate import PreGateDeps, pre_gate_implementation
from factory.runtime import PipelineRuntime
from factory.workspace import (
    ArtifactManifest,
    attempt_dir,
    compute_sha256,
    find_resumable_artifact,
    write_artifact,
)

log = structlog.get_logger()


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
    return derive_context(runtime.sub, work_item_id, role_name, spec_content=spec)


def run_worker(config: FactoryConfig, channel: Channel) -> None:
    sub = Substrate(config.dsn, config.project_name, config.hmac_key_path)
    spec_content = _load_spec(config)
    runtime = PipelineRuntime(sub=sub, config=config, spec_content=spec_content, channel=channel)
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
    channel = runtime.channel
    actor_id = config.worker_actor_id(channel.name)
    for role_name in config.worker_roles:
        sub.register_actor_role(actor_id, role_name)
    poll_interval = config.poll_interval_seconds
    shutting_down = False

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
            except Exception:
                log.exception("process_error", work_item_id=str(wi.work_item_id))
                sub.release_claim(wi.work_item_id, actor_id)
            break
        if not claimed and not shutting_down:
            time.sleep(poll_interval)
    log.info("worker_loop_exiting")


def _has_prior_gate_fail(sub: Substrate, work_item_id: str) -> bool:
    events = sub.read_events(work_item_id=work_item_id)
    return any(e.transition in (TRANSITION_GATE_FAIL, TRANSITION_CHANNEL_FAIL) for e in events)


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
    if config.use_project_venv:
        from factory.venv import ensure_project_venv

        python_executable = str(ensure_project_venv(Path(config.workspace_root)))
    return PreGateDeps(
        interface_pyi_path=interface_pyi_path,
        dep_paths=dep_pyi_paths if dep_pyi_paths else None,
        dep_spec_paths=dep_spec_paths,
        python_executable=python_executable,
        test_suite_path=test_suite_path,
    )


def process_work_item(
    runtime: PipelineRuntime,
    wi,
    actor_id: str,
    claim,
    role_name: str,
) -> None:
    sub = runtime.sub
    config = runtime.config
    channel = runtime.channel
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
    if config.per_channel_timeout and channel.name in config.per_channel_timeout:
        timeout = config.per_channel_timeout[channel.name]
    ad = attempt_dir(wr, work_item_id, attempt_number)
    prompt = render_prompt(ctx)
    invocation_start = time.monotonic()
    invoke_result = channel.invoke(role_name, prompt, ad, timeout)
    invocation_end = time.monotonic()
    duration_seconds = round(invocation_end - invocation_start, 3)
    effective_family = invoke_result.family or channel.family

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
        )
        return

    artifact_path = ad / invoke_result.artifact_name

    if role_name == ROLE_IMPLEMENTER and config.inner_gate_retries > 0:
        artifact_path, ctx, duration_seconds = _inner_gate_loop(
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
        )
        if artifact_path is None:
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
        payload=SubmitPayload(duration_seconds=duration_seconds).to_dict(),
        custom_fields={
            CUSTOM_FIELD_ARTIFACT_PATH: str(artifact_path),
            CUSTOM_FIELD_ARTIFACT_HASH: sha,
        },
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
) -> tuple[Path | None, PromptContext, float]:
    sub = runtime.sub
    work_item_id = str(wi.work_item_id)
    pre_gate_deps = _resolve_pre_gate_deps(sub, wi, config)
    max_retries = config.inner_gate_retries
    current_artifact = artifact_path
    current_ctx = ctx
    duration_seconds = round(time.monotonic() - invocation_start, 3)

    for retry in range(max_retries):
        if not current_artifact.exists():
            log.warning("inner_gate_artifact_missing", work_item_id=work_item_id)
            return current_artifact, current_ctx, duration_seconds

        pre_result = pre_gate_implementation(
            current_artifact,
            interface_pyi_path=pre_gate_deps.interface_pyi_path,
            dependency_pyi_paths=pre_gate_deps.dep_paths,
            dependency_spec_paths=pre_gate_deps.dep_spec_paths,
            python_executable=pre_gate_deps.python_executable,
            test_suite_path=pre_gate_deps.test_suite_path,
        )
        if pre_result.passed:
            log.info(
                "inner_gate_passed",
                work_item_id=work_item_id,
                retry=retry,
            )
            return current_artifact, current_ctx, duration_seconds

        log.info(
            "inner_gate_failed_retry",
            work_item_id=work_item_id,
            retry=retry,
            mypy_passed=pre_result.mypy_passed,
            ruff_passed=pre_result.ruff_passed,
            pytest_passed=pre_result.pytest_passed,
            diagnostics=pre_result.diagnostics[:3],
        )

        from factory.failure_summary import FailureEntry

        if not pre_result.mypy_passed:
            gate_label = "inner_mypy"
        elif not pre_result.ruff_passed:
            gate_label = "inner_ruff"
        else:
            gate_label = "inner_pytest"
        retry_failures = [
            *current_ctx.prior_failures,
            FailureEntry(
                attempt_number=attempt_number,
                role=role_name,
                channel=channel.name,
                gate_name=gate_label,
                diagnostic="; ".join(pre_result.diagnostics[:5]),
            ),
        ]
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
        )
        retry_prompt = render_prompt(current_ctx)
        retry_ad = attempt_dir(runtime.workspace_root, work_item_id, attempt_number)
        retry_start = time.monotonic()
        retry_result = channel.invoke(role_name, retry_prompt, retry_ad, timeout)
        duration_seconds += round(time.monotonic() - retry_start, 3)

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
            )
            return None, current_ctx, duration_seconds
        current_artifact = retry_ad / retry_result.artifact_name

    log.info(
        "inner_gate_exhausted_retries",
        work_item_id=work_item_id,
        max_retries=max_retries,
    )
    return current_artifact, current_ctx, duration_seconds


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
                        "error_message": "cannot_proceed without diagnostics file",
                        "duration_seconds": duration_seconds,
                    }
                ).to_dict(),
            )
        return
    log.error(
        "channel_invoke_failed",
        work_item_id=str(work_item_id),
        error=invoke_result.error_message,
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
                "error_message": invoke_result.error_message,
                "timed_out": invoke_result.timed_out,
                "exit_code": invoke_result.exit_code,
                "duration_seconds": duration_seconds,
            }
        ).to_dict(),
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


def _create_channel(config: FactoryConfig) -> Channel:
    channels = set(rc.channel for rc in config.roles if rc.channel != CHANNEL_CODE)
    if len(channels) == 1:
        ch = channels.pop()
        if ch == CHANNEL_OPENCODE:
            from factory.opencode_channel import OpenCodeChannel

            return OpenCodeChannel(config)
        if ch == CHANNEL_CLAUDE_CODE:
            from factory.claude_code_channel import ClaudeCodeChannel

            return ClaudeCodeChannel(config)
        raise ValueError(
            f"Unknown channel: {ch}. Supported: {CHANNEL_CLAUDE_CODE}, {CHANNEL_OPENCODE}"
        )
    raise NotImplementedError("Multi-channel dispatch not yet implemented")


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
    channel = _create_channel(config)
    run_worker(config, channel)


def main() -> None:
    _main()


if __name__ == "__main__":
    main()
