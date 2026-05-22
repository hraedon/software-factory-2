from __future__ import annotations

from pathlib import Path

from factory.constants import (
    CUSTOM_FIELD_REVIEW_FINDINGS,
    GATE_NAME_CROSS_FAMILY_REVIEW,
)
from factory.gate._base import GateResult
from factory.output_extraction import extract_json_from_output


# tier: enforce
# precondition: implementation gate passed; cross-family reviewer produces structured verdict
# audit trigger: re-evaluate if review JSON schema changes
def _extract_json_vote(path: Path) -> dict:
    """Read a JSON artifact and return the parsed vote object."""
    if not path.exists():
        return {}
    try:
        text = path.read_text()
    except Exception:
        return {}
    extracted = extract_json_from_output(text)
    if extracted is None:
        return {}
    if isinstance(extracted, dict):
        return extracted
    try:
        import json

        return json.loads(str(extracted))
    except json.JSONDecodeError:
        return {}


def evaluate_review(artifact_path: Path) -> GateResult:
    """Evaluate a cross-family review artifact.

    Expects a JSON object with `passed` (boolean), `findings` (list of dicts with
    ac_id/kind/severity/body), and `rationale` (string).

    Emits `diagnostic_kind`:
    - "review_malformed" — reviewer output was empty, unparseable, or missing required fields.
    - "review_found_defect" — reviewer produced a valid verdict that found substantive defects.
    """
    vote = _extract_json_vote(artifact_path)
    if not vote:
        return GateResult(
            passed=False,
            gate_name=GATE_NAME_CROSS_FAMILY_REVIEW,
            diagnostics=["Reviewer produced no parseable JSON output"],
            diagnostic_kind="review_malformed",
        )
    passed = bool(vote.get("passed"))
    raw_findings = vote.get("findings", [])
    if not isinstance(raw_findings, list):
        raw_findings = []
    rationale = str(vote.get("rationale", ""))
    diagnostics: list[str] = []
    structured_findings: list[dict] = []
    has_structured_findings = False
    if not passed:
        if raw_findings:
            for item in raw_findings:
                if isinstance(item, dict) and "body" in item:
                    has_structured_findings = True
                    structured_findings.append(item)
                    diagnostics.append(
                        f"[{item.get('severity', 'block')}] "
                        f"{item.get('ac_id', '')} "
                        f"({item.get('kind', 'impl')}): {item['body']}"
                    )
                else:
                    diagnostics.append(str(item))
        else:
            diagnostics.append("Review did not pass and provided no findings.")
        if rationale:
            diagnostics.append(f"Rationale: {rationale}")
    # Malformed: no parseable JSON at all, or valid JSON but missing required shape on failure
    malformed = not passed and not has_structured_findings and not rationale
    diagnostic_kind = ""
    if not passed:
        diagnostic_kind = "review_malformed" if malformed else "review_found_defect"
    routing_fields: dict = {}
    if structured_findings:
        routing_fields[CUSTOM_FIELD_REVIEW_FINDINGS] = structured_findings
    return GateResult(
        passed=passed,
        gate_name=GATE_NAME_CROSS_FAMILY_REVIEW,
        diagnostics=diagnostics,
        diagnostic_kind=diagnostic_kind,
        routing_fields=routing_fields,
    )
