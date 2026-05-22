from __future__ import annotations

from pathlib import Path

from factory.constants import GATE_NAME_OUTCOME_E2E
from factory.gate._base import GateResult
from factory.gate.review import _extract_json_vote


# tier: enforce
# precondition: integration gate passed; outcome verifier evaluates assembled product
# audit trigger: re-evaluate if outcome verification schema changes
def evaluate_outcome_verification(artifact_path: Path) -> GateResult:
    """Evaluate an outcome-verification artifact.

    Expects a JSON object with `verdict` ("pass"/"fail"/"cannot_proceed")
    and optionally `routing_hint`.
    """
    vote = _extract_json_vote(artifact_path)
    verdict = str(vote.get("verdict", "")).lower()
    passed = verdict == "pass"
    rationale = str(vote.get("rationale", ""))
    diagnostics: list[str] = []
    if verdict == "cannot_proceed":
        return GateResult(
            passed=False,
            gate_name=GATE_NAME_OUTCOME_E2E,
            diagnostics=[
                f"Outcome verifier returned cannot_proceed: {rationale or 'no rationale'}"
            ],
            diagnostic_kind="outcome_e2e",
        )
    routing_hint: dict | None = None
    if not passed:
        diagnostics.append(f"Outcome verification failed: {rationale or 'no rationale provided'}")
        vote_hint = vote.get("routing_hint")
        if isinstance(vote_hint, dict):
            hint_type = vote_hint.get("work_item_type", "unknown")
            hint_reason = vote_hint.get("reason", "")
            diagnostics.append(f"Routing hint: {hint_type} — {hint_reason}")
            routing_hint = vote_hint
    return GateResult(
        passed=passed,
        gate_name=GATE_NAME_OUTCOME_E2E,
        diagnostics=diagnostics,
        diagnostic_kind="outcome_e2e" if not passed else "",
        routing_hint=routing_hint,
    )
