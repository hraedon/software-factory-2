from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

import structlog

from factory.channel import Channel
from factory.output_extraction import extract_json_from_output

log = structlog.get_logger()


@dataclass(frozen=True)
class JurorVote:
    passed: bool
    rationale: str
    channel: str
    family: str


@dataclass(frozen=True)
class JuryVerdict:
    passed: bool
    votes_for: int
    votes_against: int
    quorum_met: bool
    verdicts: tuple[JurorVote, ...]
    disagreement_rationale: str = ""


def _parse_vote(text: str) -> dict:
    """Extract JSON vote from raw channel output."""
    extracted = extract_json_from_output(text)
    if extracted is None:
        return {}
    if isinstance(extracted, dict):
        return extracted
    try:
        return json.loads(str(extracted))
    except json.JSONDecodeError:
        return {}


def _invoke_juror(
    ch_name: str,
    channel: Channel,
    prompt: str,
    outputs_dir: Path,
    timeout: int,
    model_override: str | None = None,
    fallback_channel: Channel | None = None,
    fallback_model: str | None = None,
) -> JurorVote:
    """Invoke a single juror channel and return its vote.

    If the primary channel fails and a fallback is configured, retries
    on the fallback channel. The returned channel name reflects whichever
    channel actually produced the response.
    """
    ch_outputs = outputs_dir / ch_name
    ch_outputs.mkdir(parents=True, exist_ok=True)
    result = channel.invoke(
        "frontier_judge",
        prompt,
        ch_outputs,
        timeout,
        model_override=model_override,
    )
    effective_family = result.family or channel.family
    active_channel = ch_name

    if not result.success and fallback_channel is not None:
        log.info(
            "juror_failover_attempt",
            primary=ch_name,
            fallback=fallback_channel.name,
        )
        fb_outputs = outputs_dir / f"{ch_name}_fb"
        fb_outputs.mkdir(parents=True, exist_ok=True)
        result = fallback_channel.invoke(
            "frontier_judge",
            prompt,
            fb_outputs,
            timeout,
            model_override=fallback_model,
        )
        effective_family = result.family or fallback_channel.family
        active_channel = f"{ch_name}_fb"
        if not result.success:
            log.warning(
                "juror_failover_failed",
                primary=ch_name,
                fallback=fallback_channel.name,
                error=result.error_message,
            )

    if not result.success:
        return JurorVote(
            passed=False,
            rationale=result.error_message or "channel failure",
            channel=active_channel,
            family=effective_family,
        )
    outputs = fb_outputs if active_channel.endswith("_fb") else ch_outputs
    artifact_path = outputs / result.artifact_name
    raw = artifact_path.read_text() if artifact_path.exists() else ""
    vote_data = _parse_vote(raw)
    return JurorVote(
        passed=bool(vote_data.get("passed")),
        rationale=str(vote_data.get("rationale", "")),
        channel=active_channel,
        family=effective_family,
    )


def run_jury(
    channels: dict[str, Channel],
    prompt: str,
    outputs_dir: Path,
    timeout: int,
    quorum: int = 2,
    models: dict[str, str | None] | None = None,
    fallback_channels: dict[str, Channel | None] | None = None,
    fallback_models: dict[str, str | None] | None = None,
) -> JuryVerdict:
    """Invoke each configured juror channel in parallel and compute a quorum verdict."""
    votes: list[JurorVote] = []
    with ThreadPoolExecutor(max_workers=len(channels)) as pool:
        futures = {
            pool.submit(
                _invoke_juror,
                ch_name,
                ch,
                prompt,
                outputs_dir,
                timeout,
                model_override=(models or {}).get(ch_name),
                fallback_channel=(fallback_channels or {}).get(ch_name),
                fallback_model=(fallback_models or {}).get(ch_name),
            ): ch_name
            for ch_name, ch in channels.items()
        }
        for future in as_completed(futures):
            ch_name = futures[future]
            try:
                vote = future.result()
            except Exception:
                log.exception("juror_invoke_failed", channel=ch_name)
                vote = JurorVote(
                    passed=False,
                    rationale="juror invocation raised an exception",
                    channel=ch_name,
                    family="unknown",
                )
            votes.append(vote)

    votes_for = sum(1 for v in votes if v.passed)
    votes_against = len(votes) - votes_for
    quorum_met = votes_for >= quorum

    disagreement_rationale = ""
    if not quorum_met:
        if votes_for > 0 and votes_against > 0:
            for_votes = "; ".join(f"{v.channel}: {v.rationale}" for v in votes if v.passed)
            against_votes = "; ".join(f"{v.channel}: {v.rationale}" for v in votes if not v.passed)
            disagreement_rationale = f"For: {for_votes} | Against: {against_votes}"
        elif votes_for == 0:
            against_votes = "; ".join(f"{v.channel}: {v.rationale}" for v in votes if not v.passed)
            disagreement_rationale = f"[all_against] {against_votes}"

    passed = quorum_met
    return JuryVerdict(
        passed=passed,
        votes_for=votes_for,
        votes_against=votes_against,
        quorum_met=quorum_met,
        verdicts=tuple(votes),
        disagreement_rationale=disagreement_rationale,
    )
