from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from factory.channel import Channel
from factory.output_extraction import extract_json_from_output


@dataclass(frozen=True)
class ReviewResult:
    passed: bool
    rationale: str
    findings: tuple[str, ...]


def _parse_review(text: str) -> dict:
    """Extract JSON review result from raw channel output."""
    extracted = extract_json_from_output(text)
    if extracted is None:
        return {}
    if isinstance(extracted, dict):
        return extracted
    return {}


def run_review(
    channel: Channel,
    prompt: str,
    outputs_dir: Path,
    timeout: int,
) -> ReviewResult:
    """Invoke a single cross-family reviewer channel and parse structured output."""
    result = channel.invoke("cross_family_reviewer", prompt, outputs_dir, timeout)
    if not result.success:
        return ReviewResult(
            passed=False,
            rationale=result.error_message or "channel failure",
            findings=(),
        )
    artifact_path = outputs_dir / result.artifact_name
    raw = artifact_path.read_text() if artifact_path.exists() else ""
    review_data = _parse_review(raw)
    findings = review_data.get("findings", [])
    if not isinstance(findings, list):
        findings = []
    return ReviewResult(
        passed=bool(review_data.get("passed")),
        rationale=str(review_data.get("rationale", "")),
        findings=tuple(str(f) for f in findings),
    )
