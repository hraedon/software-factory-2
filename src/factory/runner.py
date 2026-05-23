from __future__ import annotations

import argparse
import threading
import time
from pathlib import Path

import structlog
from substrate import ActorMetadata, Substrate
from substrate._errors import ErrorCode, SubstrateError

from factory.channel import Channel, ChannelDisabledError
from factory.config import FactoryConfig, load_config
from factory.constants import (
    CHANNEL_CLAUDE_CODE,
    CHANNEL_CODE,
    CHANNEL_GEMINI_CLI,
    CHANNEL_OPENCODE,
    CUSTOM_FIELD_ARTIFACT_HASH,
    CUSTOM_FIELD_ARTIFACT_PATH,
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
from factory.idempotency import make_event_id
from factory.inner_gate import (
    _build_export_map,  # noqa: F401 - re-exported for test compatibility
    _handle_invoke_failure,
    _inner_gate_label,  # noqa: F401 - re-exported for test compatibility
    _inner_gate_loop,
    _resolve_pre_gate_deps,  # noqa: F401 - re-exported for test compatibility
    _run_pre_gate,  # noqa: F401 - re-exported for test compatibility
    _should_failover,
)
from factory.jury_orchestrator import (
    _process_jury_work_item,
    _resolve_jury_channels,  # noqa: F401 - re-exported for test compatibility
)
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
            claim = sub.acquire_claim(
                wi.work_item_id,
                actor_id,
                config.claim_ttl_seconds,
                event_id=make_event_id(wi.work_item_id, "acquire_claim", 0),
            )
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
                    event_id=make_event_id(
                        wi.work_item_id, TRANSITION_CLAIM, claim.attempt_number, extra="budget"
                    ),
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
                    event_id=make_event_id(
                        wi.work_item_id,
                        TRANSITION_ROUTE_TO_CANNOT_PROCEED,
                        claim.attempt_number,
                        extra="budget",
                    ),
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
                event_id=make_event_id(wi.work_item_id, TRANSITION_CLAIM, claim.attempt_number),
            )
            log.info(
                "claim_acquired",
                work_item_id=str(wi.work_item_id),
                attempt=claim.attempt_number,
            )
            from factory.heartbeat import HeartbeatSession

            try:
                with HeartbeatSession(
                    sub,
                    wi.work_item_id,
                    actor_id,
                    claim.attempt_number,
                    config.claim_ttl_seconds,
                ) as heartbeat:
                    process_work_item(
                        runtime,
                        wi,
                        actor_id,
                        claim,
                        role_name,
                        cancel_event=heartbeat.cancel_event,
                    )
                claimed = True
                channel_consecutive_failures.pop(channel.name, None)
                channel_backoff_until.pop(channel.name, None)
            except Exception:
                log.exception("process_error", work_item_id=str(wi.work_item_id))
                try:
                    sub.release_claim(
                        wi.work_item_id,
                        actor_id,
                        event_id=make_event_id(
                            wi.work_item_id, "release_claim", claim.attempt_number, extra="error"
                        ),
                    )
                except SubstrateError as exc:
                    if exc.code == ErrorCode.CLAIM_LOST:
                        log.warning(
                            "release_after_claim_lost",
                            work_item_id=str(wi.work_item_id),
                        )
                    else:
                        raise
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


def process_work_item(
    runtime: PipelineRuntime,
    wi,
    actor_id: str,
    claim,
    role_name: str,
    cancel_event: threading.Event | None = None,
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
            cancel_event=cancel_event,
        )
        return

    channel = runtime.channel_for_role(role_name)
    if config.per_channel_timeout and channel.name in config.per_channel_timeout:
        timeout = config.per_channel_timeout[channel.name]
    prompt = render_prompt(ctx)
    invocation_start = time.monotonic()
    invoke_kwargs: dict = {"extra_env": extra_env}
    if cancel_event is not None:
        invoke_kwargs["cancel_event"] = cancel_event
    invoke_result = channel.invoke(role_name, prompt, ad, timeout, **invoke_kwargs)
    invocation_end = time.monotonic()
    if cancel_event is not None and cancel_event.is_set():
        log.warning(
            "abandoning_invocation_after_claim_lost",
            work_item_id=work_item_id,
            attempt=attempt_number,
            role=role_name,
        )
        return
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
            fb_kwargs: dict = {
                "extra_env": extra_env,
                "model_override": fallback_model,
            }
            if cancel_event is not None:
                fb_kwargs["cancel_event"] = cancel_event
            invoke_result = fb_channel.invoke(
                role_name,
                prompt,
                ad,
                timeout,
                **fb_kwargs,
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
            event_id=make_event_id(
                wi.work_item_id, TRANSITION_CHANNEL_FAIL, attempt_number, extra="oversized"
            ),
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
        model=invoke_result.model,
        context_hash=ctx.context_hash,
    )
    write_artifact(ad, invoke_result.artifact_name, artifact_data, manifest)
    actor_metadata = ActorMetadata(
        role=role_name,
        channel=channel.name,
        family=effective_family,
        model=invoke_result.model,
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
        event_id=make_event_id(wi.work_item_id, TRANSITION_SUBMIT, attempt_number),
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
        event_id=make_event_id(
            wi.work_item_id, TRANSITION_SUBMIT, resumable_attempt, extra="resume"
        ),
    )


_CHANNEL_CONSTRUCTORS: dict[str, type[Channel]] = {}

# tier: enforce
# precondition: AGENTS.md "channel status" table is the source of truth for
#   declared status; this dict must match it whenever any channel moves between
#   validated / unvalidated / disabled. See BC-194 and RFC-037.
# audit trigger: re-evaluate when any channel changes validated/unvalidated/disabled status
_CHANNEL_STATUS: dict[str, str] = {
    CHANNEL_CLAUDE_CODE: "validated",
    CHANNEL_OPENCODE: "validated",
    CHANNEL_GEMINI_CLI: "disabled",
}


def _register_channel(channel_name: str, import_path: str, class_name: str) -> None:
    import importlib

    _CHANNEL_CONSTRUCTORS[channel_name] = getattr(importlib.import_module(import_path), class_name)


_register_channel(CHANNEL_OPENCODE, "factory.opencode_channel", "OpenCodeChannel")
_register_channel(CHANNEL_CLAUDE_CODE, "factory.claude_code_channel", "ClaudeCodeChannel")
_register_channel(CHANNEL_GEMINI_CLI, "factory.gemini_channel", "GeminiCLIChannel")

_SUPPORTED_CHANNEL_NAMES = ", ".join(sorted(_CHANNEL_CONSTRUCTORS))


def _create_channels(config: FactoryConfig) -> dict[str, Channel]:
    import warnings

    channel_names = set(rc.channel for rc in config.roles if rc.channel != CHANNEL_CODE)
    channels: dict[str, Channel] = {}
    for ch_name in channel_names:
        status = _CHANNEL_STATUS.get(ch_name, "unvalidated")
        if status == "disabled":
            raise ChannelDisabledError(
                f"Channel '{ch_name}' is disabled; see AGENTS.md for current channel status."
            )
        if status == "unvalidated":
            warnings.warn(
                f"Channel '{ch_name}' is unvalidated; results may be unreliable. "
                "See AGENTS.md for current channel status.",
                stacklevel=2,
            )
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
