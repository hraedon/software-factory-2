from __future__ import annotations

from pathlib import Path

from factory.constants import GATE_NAME_BEHAVIORAL
from factory.gate import GateResult


def evaluate_behavioral(
    artifact_path: Path,
    scenarios: list[dict] | None = None,
) -> GateResult:
    if not scenarios:
        return GateResult(
            passed=True,
            gate_name=GATE_NAME_BEHAVIORAL,
            diagnostics=[],
            skipped=True,
        )
    raise NotImplementedError("behavioral gate scheduled for Phase 5; see plans/behavioral-gate.md")
