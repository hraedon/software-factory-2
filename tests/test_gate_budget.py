"""Test that mechanical gate count stays within the spec §10 phase budget.

Spec §10 "Mechanical gate budget":
- Phase 3 max: 12 gates
- A "mechanical gate" is any deterministic, non-model evaluation applied to an
  artifact: syntax checks, type checks, linters, test runners, structural
  validators, import smoke tests, artifact size guards, and their inner-gate
  equivalents.
- A new gate is justified only after prompt change, role boundary change, spec
  clarification, and defect-class systemic fix have been attempted and failed.

This test enforces the budget at the code level. If it fails, the response is
not "raise the limit" — it is "justify the new gate per spec §10, or remove an
existing gate that has not fired in the last 3 golden runs."
"""

from __future__ import annotations

import inspect

import factory.gate as gate_module
import factory.pre_gate as pre_gate_module

# Spec §10 budget per phase
_PHASE_BUDGET = {
    1: 3,
    2: 8,
    3: 12,
    4: 15,
    5: 18,
}


def _count_gate_entry_points(module) -> int:
    """Count public evaluate_* and pre_gate_* functions as gate entry points."""
    prefix = module.__name__.split(".")[-1].replace("_", "")
    if prefix == "gate":
        prefix = "evaluate_"
    elif prefix == "pregate":
        prefix = "pre_gate_"
    else:
        prefix = "evaluate_"

    count = 0
    for name, obj in inspect.getmembers(module, inspect.isfunction):
        if name.startswith("evaluate_") or name.startswith("pre_gate_"):
            # Exclude helper/private functions
            if not name.startswith("_"):
                count += 1
    return count


def test_gate_count_within_phase_3_budget():
    """Phase 3 gate count must not exceed the spec §10 budget of 12."""
    outer = _count_gate_entry_points(gate_module)
    inner = _count_gate_entry_points(pre_gate_module)
    total = outer + inner

    budget = _PHASE_BUDGET[3]
    assert total <= budget, (
        f"Phase 3 mechanical gate count {total} exceeds budget {budget}. "
        f"(outer={outer}, inner={inner}). "
        f"Per spec §10, the response is not a higher limit; it is a prompt/role/spec "
        f"change, or a spec amendment with rationale if all other responses failed."
    )


def test_phase_budgets_are_monotonic():
    """Later phases must have equal or larger budgets than earlier phases."""
    budgets = list(_PHASE_BUDGET.values())
    assert budgets == sorted(budgets), "Phase budgets must be monotonically increasing"
