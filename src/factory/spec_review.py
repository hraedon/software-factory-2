"""Spec review — model-mediated architectural review before decomposition.

Runs before populate_work_items to catch composition gaps (orphaned definitions,
missing runtime context, write-only data paths, missing lifecycle hooks) that
the socratic-specification process may have missed.  Each finding includes an
inferred answer and confidence score; findings above the confidence threshold
are auto-resolved and recorded, while low-confidence findings are surfaced to
the principal.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import structlog

from factory.channel import Channel
from factory.config import FactoryConfig

log = structlog.get_logger()


@dataclass(frozen=True)
class SpecReviewFinding:
    """A single gap identified by the spec reviewer."""

    pattern: str
    module: str
    symbol: str
    detail: str
    inferred_answer: str | None = None
    confidence: float = 0.0
    severity: str = "medium"

    @property
    def is_auto_resolved(self) -> bool:
        return self.inferred_answer is not None and self.confidence >= 0.7


@dataclass(frozen=True)
class SpecReviewResult:
    """Result of a spec review pass."""

    findings: list[SpecReviewFinding] = field(default_factory=list)
    confidence_threshold: float = 0.7
    raw_output: str = ""

    @property
    def passed(self) -> bool:
        return len(self.surfaced_findings) == 0

    @property
    def auto_resolved_findings(self) -> list[SpecReviewFinding]:
        return [f for f in self.findings if f.confidence >= self.confidence_threshold]

    @property
    def surfaced_findings(self) -> list[SpecReviewFinding]:
        return [f for f in self.findings if f.confidence < self.confidence_threshold]

    def summary(self) -> str:
        if not self.findings:
            return "Spec review: no composition gaps found."
        auto = len(self.auto_resolved_findings)
        surfaced = len(self.surfaced_findings)
        parts = [f"Spec review: {len(self.findings)} findings"]
        if auto:
            parts.append(f"{auto} auto-resolved at confidence >= {self.confidence_threshold}")
        if surfaced:
            parts.append(f"{surfaced} surfaced for human review")
        return "; ".join(parts) + "."


def load_spec_for_review(spec_path: Path) -> str:
    """Load spec text from a .md or .yaml file."""
    if not spec_path.exists():
        raise FileNotFoundError(f"Spec not found: {spec_path}")
    if spec_path.suffix in (".yaml", ".yml"):
        import yaml

        data = yaml.safe_load(spec_path.read_text())
        return json.dumps(data, indent=2, ensure_ascii=False)
    return spec_path.read_text()


def _build_review_prompt(spec_text: str) -> str:
    """Build the review prompt from template + spec text."""
    prompt_path = Path(__file__).parent / "prompts" / "spec_review.md"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt template not found: {prompt_path}")
    template = prompt_path.read_text()
    parts = [template, "", "---", "", "## Spec to review", "", spec_text]
    return "\n".join(parts)


def _parse_review_json(raw_text: str) -> list[dict]:
    """Extract findings JSON array from model output."""
    # Try fenced JSON blocks first
    json_match = re.findall(r"```(?:json)?\s*\n(.*?)\n```", raw_text, re.DOTALL)
    if json_match:
        last = json_match[-1].strip()
    else:
        last = raw_text.strip()

    # Try direct parse
    try:
        data = json.loads(last)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "findings" in data:
            return data["findings"]
    except json.JSONDecodeError:
        pass

    # Try raw_decode scan
    decoder = json.JSONDecoder()
    idx = 0
    while idx < len(last):
        char = last[idx]
        if char in " \t\n\r":
            idx += 1
            continue
        if char in "[{":
            try:
                obj, end = decoder.raw_decode(last, idx)
                if isinstance(obj, list):
                    return obj
                if isinstance(obj, dict) and "findings" in obj:
                    return obj["findings"]
                idx += end
                continue
            except json.JSONDecodeError:
                pass
        idx += 1

    return []


def _finding_from_dict(d: dict) -> SpecReviewFinding:
    """Convert a raw dict to a SpecReviewFinding, with safe defaults."""
    raw_confidence = d.get("confidence", 0.0)
    confidence = float(raw_confidence) if raw_confidence is not None else 0.0
    return SpecReviewFinding(
        pattern=str(d.get("pattern", "unknown")),
        module=str(d.get("module", "unknown")),
        symbol=str(d.get("symbol", "unknown")),
        detail=str(d.get("detail", "")),
        inferred_answer=d.get("inferred_answer"),
        confidence=confidence,
        severity=str(d.get("severity", "medium")),
    )


def review_spec(
    channel: Channel,
    config: FactoryConfig,
    spec_path: Path,
    confidence_threshold: float = 0.7,
) -> SpecReviewResult:
    """Run a model-mediated architectural review on a spec.

    Args:
        channel: Model channel to use for the review.
        config: Factory configuration.
        spec_path: Path to spec.md or spec.yaml.
        confidence_threshold: Findings with confidence >= this are auto-resolved.

    Returns:
        SpecReviewResult with findings, auto-resolved/surfaced split, and summary.
    """
    import tempfile

    spec_text = load_spec_for_review(spec_path)
    prompt = _build_review_prompt(spec_text)

    with tempfile.TemporaryDirectory(prefix="sf2_spec_review_") as tmpdir:
        outputs_dir = Path(tmpdir)
        log.info("spec_review.invoke", spec=str(spec_path), channel=channel.name)
        result = channel.invoke(
            role="interface_architect",
            prompt=prompt,
            outputs_dir=outputs_dir,
            timeout=120,
        )

        if not result.success:
            log.warning(
                "spec_review_channel_failed",
                error=result.error_message,
                exit_code=result.exit_code,
            )
            return SpecReviewResult(
                findings=[],
                confidence_threshold=confidence_threshold,
                raw_output=result.error_message or "",
            )

        # Read output from artifact or raw stdout
        raw_output = ""
        if result.artifact_name:
            artifact_path = outputs_dir / result.artifact_name
            if artifact_path.exists():
                raw_output = artifact_path.read_text()
        if not raw_output:
            stdout_path = outputs_dir / "raw_stdout.txt"
            if stdout_path.exists():
                raw_output = stdout_path.read_text()

    raw_findings = _parse_review_json(raw_output)
    findings = [_finding_from_dict(d) for d in raw_findings]

    log.info(
        "spec_review.complete",
        total=len(findings),
        auto_resolved=sum(1 for f in findings if f.confidence >= confidence_threshold),
        surfaced=sum(1 for f in findings if f.confidence < confidence_threshold),
    )

    return SpecReviewResult(
        findings=findings,
        confidence_threshold=confidence_threshold,
        raw_output=raw_output,
    )


def format_review_output(result: SpecReviewResult) -> str:
    """Format a review result for human-readable CLI output."""
    lines: list[str] = [result.summary(), ""]

    for f in result.surfaced_findings:
        lines.append(f"SURFACED (confidence {f.confidence:.2f}):")
        lines.append(f"  [{f.pattern}] {f.module} module, {f.symbol}")
        lines.append(f"    {f.detail}")
        if f.inferred_answer:
            lines.append(f"    Suggested: {f.inferred_answer}")
        lines.append("")

    for f in result.auto_resolved_findings:
        lines.append(f"AUTO-RESOLVED (confidence {f.confidence:.2f}):")
        lines.append(f"  [{f.pattern}] {f.module} module, {f.symbol}")
        lines.append(f"    {f.detail}")
        if f.inferred_answer:
            lines.append(f"    Inferred: {f.inferred_answer}")
        lines.append("")

    return "\n".join(lines)
