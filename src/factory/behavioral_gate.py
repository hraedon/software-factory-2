from __future__ import annotations

from pathlib import Path

from factory.gate import GateResult


def evaluate_behavioral(
    artifact_path: Path,
    scenarios: list[dict] | None = None,
) -> GateResult:
    """Behavioral gate stub.

    The behavioral gate evaluates an implementation against end-to-end scenarios
    (e.g., HTTP requests, UI interactions, CLI invocations).  It sits between
    the mechanical gates (Stage 5) and the frontier judge (Stage 7).

    For now, when ``scenarios`` is empty the gate is skipped.  When scenarios
    are present it raises ``NotImplementedError`` — the full implementation is
    scheduled for Phase 5.
    """
    if not scenarios:
        return GateResult(
            passed=True,
            gate_name="behavioral",
            diagnostics=[],
            skipped=True,
        )
    raise NotImplementedError("behavioral gate scheduled for Phase 5; see plans/behavioral-gate.md")
