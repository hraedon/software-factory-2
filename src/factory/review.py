from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from factory.channel import Channel
from factory.constants import ROLE_CROSS_FAMILY_REVIEWER
from factory.output_extraction import extract_json_from_output


@dataclass(frozen=True)
class ReviewFinding:
    ac_id: str
    kind: str  # "impl" or "test"
    severity: str  # "block" or "advise"
    body: str


@dataclass(frozen=True)
class ReviewResult:
    passed: bool
    rationale: str
    findings: tuple[ReviewFinding, ...]
    malformed: bool = False  # True if reviewer output was invalid / refused / not JSON


def _parse_review(text: str) -> dict:
    """Extract JSON review result from raw channel output."""
    extracted = extract_json_from_output(text)
    if extracted is None:
        return {}
    if isinstance(extracted, dict):
        return extracted
    return {}


def _parse_findings(raw_findings: list) -> tuple[ReviewFinding, ...]:
    findings: list[ReviewFinding] = []
    for item in raw_findings:
        if isinstance(item, dict):
            findings.append(
                ReviewFinding(
                    ac_id=str(item.get("ac_id", "")),
                    kind=str(item.get("kind", "impl")),
                    severity=str(item.get("severity", "block")),
                    body=str(item.get("body", "")),
                )
            )
        elif isinstance(item, str):
            # Legacy string format (Phase 4): treat as block-level impl finding
            findings.append(ReviewFinding(ac_id="", kind="impl", severity="block", body=item))
    return tuple(findings)


def run_review(
    channel: Channel,
    prompt: str,
    outputs_dir: Path,
    timeout: int,
) -> ReviewResult:
    """Invoke a single cross-family reviewer channel and parse structured output."""
    result = channel.invoke(ROLE_CROSS_FAMILY_REVIEWER, prompt, outputs_dir, timeout)
    if not result.success:
        return ReviewResult(
            passed=False,
            rationale=result.error_message or "channel failure",
            findings=(),
            malformed=True,
        )
    artifact_path = outputs_dir / result.artifact_name
    raw = artifact_path.read_text() if artifact_path.exists() else ""
    review_data = _parse_review(raw)
    if not review_data:
        return ReviewResult(
            passed=False,
            rationale="Reviewer produced no parseable JSON output",
            findings=(),
            malformed=True,
        )
    passed = bool(review_data.get("passed"))
    raw_findings = review_data.get("findings", [])
    if not isinstance(raw_findings, list):
        raw_findings = []
    findings = _parse_findings(raw_findings)
    rationale = str(review_data.get("rationale", ""))
    # Malformed if reviewer output is valid JSON but missing required shape
    malformed = not passed and not findings and not rationale
    return ReviewResult(
        passed=passed,
        rationale=rationale,
        findings=findings,
        malformed=malformed,
    )
