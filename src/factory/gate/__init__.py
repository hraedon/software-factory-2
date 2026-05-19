"""factory.gate — backward-compatible re-export shim.

All public names from the original gate.py are re-exported here so that every
existing import site continues to work without modification.
"""

from __future__ import annotations

# Core result type and size guard
from factory.gate._base import GateResult, _guard_artifact_size

# Shared pyi utilities (used by runner.py, context.py, and test files)
from factory.gate._pyi_utils import (
    extract_exports,
    structural_signature,
    structurally_equivalent_pyi,
)

# Subprocess helpers (exposed so test_gate_budget.py can patch via gate_module)
from factory.gate._subprocess import (
    _run_mypy,
    _run_pytest,
    _run_pytest_collect,
    _run_ruff,
)

# Gate evaluators
from factory.gate.implementation import evaluate_implementation
from factory.gate.integration import evaluate_integration
from factory.gate.interface_spec import evaluate_interface_spec
from factory.gate.jury import evaluate_jury
from factory.gate.outcome import evaluate_outcome_verification
from factory.gate.review import evaluate_review
from factory.gate.test_suite import evaluate_test_suite

__all__ = [
    "GateResult",
    "_guard_artifact_size",
    "_run_mypy",
    "_run_pytest",
    "_run_pytest_collect",
    "_run_ruff",
    "evaluate_implementation",
    "evaluate_integration",
    "evaluate_interface_spec",
    "evaluate_jury",
    "evaluate_outcome_verification",
    "evaluate_review",
    "evaluate_test_suite",
    "extract_exports",
    "structural_signature",
    "structurally_equivalent_pyi",
]
