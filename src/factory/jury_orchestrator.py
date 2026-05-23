from __future__ import annotations

import json
import threading
from pathlib import Path

import structlog
from substrate import ActorMetadata

from factory.channel import Channel
from factory.config import FactoryConfig
from factory.constants import (
    ARTIFACT_FILENAME_JURY_VERDICT,
    CUSTOM_FIELD_ARTIFACT_HASH,
    CUSTOM_FIELD_ARTIFACT_PATH,
    ROLE_FRONTIER_JUDGE,
    TRANSITION_CHANNEL_FAIL,
    TRANSITION_SUBMIT,
)
from factory.context import PromptContext, render_prompt
from factory.event_schemas import ChannelFailPayload
from factory.idempotency import make_event_id
from factory.runtime import PipelineRuntime
from factory.workspace import ArtifactManifest, compute_sha256, write_artifact

log = structlog.get_logger()


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
    cancel_event: threading.Event | None = None,
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
            event_id=make_event_id(
                wi.work_item_id, TRANSITION_CHANNEL_FAIL, attempt_number, extra="no_jury"
            ),
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
        if cancel_event is not None and cancel_event.is_set():
            log.warning(
                "abandoning_jury_after_claim_lost",
                work_item_id=work_item_id,
            )
            return
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
            event_id=make_event_id(
                wi.work_item_id, TRANSITION_CHANNEL_FAIL, attempt_number, extra="jury_exc"
            ),
        )
        return
    if cancel_event is not None and cancel_event.is_set():
        log.warning(
            "abandoning_jury_verdict_after_claim_lost",
            work_item_id=work_item_id,
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
        # RFC-034: jury aggregate spans multiple jurors with potentially
        # different models — no single resolved model applies. None is
        # correct here, not a gap.
        model=None,
        context_hash=ctx.context_hash,
    )
    write_artifact(ad, ARTIFACT_FILENAME_JURY_VERDICT, artifact_data, manifest)
    actor_metadata = ActorMetadata(
        role=ROLE_FRONTIER_JUDGE,
        channel="jury_aggregate",
        family="multi",
        model=None,
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
        event_id=make_event_id(wi.work_item_id, TRANSITION_SUBMIT, attempt_number),
    )
