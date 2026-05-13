from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from factory.channel import Channel
from factory.output_extraction import extract_json_from_output


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


def run_jury(
    channels: dict[str, Channel],
    prompt: str,
    outputs_dir: Path,
    timeout: int,
    quorum: int = 2,
) -> JuryVerdict:
    """Invoke each configured juror channel sequentially and compute a quorum verdict.

    Parallel invocation is deferred to a later optimization; the interface
    (JuryVerdict) will remain unchanged.
    """
    votes: list[JurorVote] = []
    for ch_name, channel in channels.items():
        ch_outputs = outputs_dir / ch_name
        ch_outputs.mkdir(parents=True, exist_ok=True)
        result = channel.invoke("frontier_judge", prompt, ch_outputs, timeout)
        effective_family = result.family or channel.family
        if not result.success:
            votes.append(
                JurorVote(
                    passed=False,
                    rationale=result.error_message or "channel failure",
                    channel=ch_name,
                    family=effective_family,
                )
            )
            continue
        artifact_path = ch_outputs / result.artifact_name
        raw = artifact_path.read_text() if artifact_path.exists() else ""
        vote_data = _parse_vote(raw)
        votes.append(
            JurorVote(
                passed=bool(vote_data.get("passed")),
                rationale=str(vote_data.get("rationale", "")),
                channel=ch_name,
                family=effective_family,
            )
        )

    votes_for = sum(1 for v in votes if v.passed)
    votes_against = len(votes) - votes_for
    quorum_met = votes_for >= quorum

    disagreement_rationale = ""
    if not quorum_met and votes_for > 0 and votes_against > 0:
        for_votes = "; ".join(f"{v.channel}: {v.rationale}" for v in votes if v.passed)
        against_votes = "; ".join(f"{v.channel}: {v.rationale}" for v in votes if not v.passed)
        disagreement_rationale = f"For: {for_votes} | Against: {against_votes}"

    passed = quorum_met
    return JuryVerdict(
        passed=passed,
        votes_for=votes_for,
        votes_against=votes_against,
        quorum_met=quorum_met,
        verdicts=tuple(votes),
        disagreement_rationale=disagreement_rationale,
    )
