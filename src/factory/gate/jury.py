from __future__ import annotations

from pathlib import Path

from factory.constants import (
    GATE_NAME_JURY_DISAGREE,
    GATE_NAME_JURY_QUORUM,
    DiagnosticKind,
)
from factory.gate._base import GateResult
from factory.gate.review import _extract_json_vote


# tier: enforce
# precondition: review gate passed; multi-model jury produces quorum verdict
# audit trigger: re-evaluate if jury quorum logic changes
def evaluate_jury(artifact_path: Path) -> GateResult:
    """Evaluate a jury verdict artifact.

    Expects a JSON object with `quorum_met` (boolean), `votes_for`, `votes_against`,
    and optionally `disagreement_rationale`.
    """
    vote = _extract_json_vote(artifact_path)
    quorum_met = bool(vote.get("quorum_met"))
    passed = quorum_met
    votes_for = int(vote.get("votes_for", 0))
    votes_against = int(vote.get("votes_against", 0))
    disagreement = str(vote.get("disagreement_rationale", ""))
    diagnostics: list[str] = []
    if not passed:
        diagnostics.append(f"Jury quorum not met ({votes_for} for, {votes_against} against).")
        if disagreement.startswith("[all_against]"):
            diagnostics.append(f"All jurors against: {disagreement.removeprefix('[all_against] ')}")
        elif disagreement:
            diagnostics.append(f"Disagreement: {disagreement}")
    gate_name = GATE_NAME_JURY_QUORUM if passed else GATE_NAME_JURY_DISAGREE
    return GateResult(
        passed=passed,
        gate_name=gate_name,
        diagnostics=diagnostics,
        diagnostic_kind=DiagnosticKind.JURY if not passed else "",
    )
