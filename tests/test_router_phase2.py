from __future__ import annotations

from factory.constants import (
    GATE_NAME_IMPLEMENTATION_IMPORT_FORBIDDEN,
    GATE_NAME_IMPLEMENTATION_LINT,
    GATE_NAME_IMPLEMENTATION_MYPY,
    GATE_NAME_IMPLEMENTATION_PYTEST,
    GATE_NAME_INTERFACE_SPEC_SYNTAX,
    GATE_NAME_TEST_SUITE_COLLECT,
    GATE_NAME_TEST_SUITE_IMPORT_FORBIDDEN,
)
from factory.gate import GateResult
from factory.router import _PHASE2_DISPATCH, DiagnosticKind, route


class TestPhase2Dispatch:
    def test_test_ac_binding_routes_to_test_author(self):
        gate = GateResult(
            passed=False,
            gate_name="test_suite_ac_binding",
            diagnostics=["AC-01 not in test"],
            diagnostic_kind="test_ac_binding",
        )
        result = route("gating", "gate_fail", gate_result=gate)
        assert result.target_state == "new"
        assert result.diagnostic_kind == DiagnosticKind.TEST_AC_BINDING

    def test_test_collect_routes_to_test_author(self):
        gate = GateResult(
            passed=False,
            gate_name=GATE_NAME_TEST_SUITE_COLLECT,
            diagnostics=["pytest --collect-only failed"],
            diagnostic_kind="test_collect",
        )
        result = route("gating", "gate_fail", gate_result=gate)
        assert result.target_state == "new"
        assert result.diagnostic_kind == DiagnosticKind.TEST_COLLECT

    def test_test_import_forbidden_routes_to_test_author(self):
        gate = GateResult(
            passed=False,
            gate_name=GATE_NAME_TEST_SUITE_IMPORT_FORBIDDEN,
            diagnostics=["Test imports _impl"],
            diagnostic_kind="test_import_forbidden",
        )
        result = route("gating", "gate_fail", gate_result=gate)
        assert result.target_state == "new"
        assert result.diagnostic_kind == DiagnosticKind.TEST_IMPORT_FORBIDDEN

    def test_impl_mypy_routes_to_implementer(self):
        gate = GateResult(
            passed=False,
            gate_name=GATE_NAME_IMPLEMENTATION_MYPY,
            diagnostics=["Incompatible return type"],
            diagnostic_kind="impl_mypy",
        )
        result = route("gating", "gate_fail", gate_result=gate)
        assert result.target_state == "new"
        assert result.diagnostic_kind == DiagnosticKind.IMPL_MYPY

    def test_impl_pytest_routes_to_implementer(self):
        gate = GateResult(
            passed=False,
            gate_name=GATE_NAME_IMPLEMENTATION_PYTEST,
            diagnostics=["FAILED test_foo - AssertionError"],
            diagnostic_kind="impl_pytest",
        )
        result = route("gating", "gate_fail", gate_result=gate)
        assert result.target_state == "new"
        assert result.diagnostic_kind == DiagnosticKind.IMPL_PYTEST

    def test_impl_lint_routes_to_implementer(self):
        gate = GateResult(
            passed=False,
            gate_name=GATE_NAME_IMPLEMENTATION_LINT,
            diagnostics=["Ruff: unused import"],
            diagnostic_kind="impl_lint",
        )
        result = route("gating", "gate_fail", gate_result=gate)
        assert result.target_state == "new"
        assert result.diagnostic_kind == DiagnosticKind.IMPL_LINT

    def test_impl_import_routes_to_implementer(self):
        gate = GateResult(
            passed=False,
            gate_name=GATE_NAME_IMPLEMENTATION_IMPORT_FORBIDDEN,
            diagnostics=["Implementation imports pytest"],
            diagnostic_kind="impl_import",
        )
        result = route("gating", "gate_fail", gate_result=gate)
        assert result.target_state == "new"
        assert result.diagnostic_kind == DiagnosticKind.IMPL_IMPORT


class TestCrossStageEscalation:
    def test_impl_failure_below_threshold_routes_normally(self):
        gate = GateResult(
            passed=False,
            gate_name=GATE_NAME_IMPLEMENTATION_PYTEST,
            diagnostics=["FAILED test"],
            diagnostic_kind="impl_pytest",
        )
        result = route(
            "gating",
            "gate_fail",
            gate_result=gate,
            attempt_number=1,
            attempt_threshold=3,
        )
        assert result.target_state == "new"
        assert result.diagnostic_kind == DiagnosticKind.IMPL_PYTEST

    def test_impl_failure_at_threshold_escalates_to_interface_architect(self):
        gate = GateResult(
            passed=False,
            gate_name=GATE_NAME_IMPLEMENTATION_PYTEST,
            diagnostics=["FAILED test"],
            diagnostic_kind="impl_pytest",
        )
        result = route(
            "gating",
            "gate_fail",
            gate_result=gate,
            attempt_number=3,
            attempt_threshold=3,
        )
        assert result.target_state == "cannot_proceed"
        assert result.diagnostic_kind == DiagnosticKind.CANNOT_PROCEED_SEAM
        diag = result.custom_fields_update["diagnostics"]
        assert diag["escalated_from_kind"] == "impl_pytest"
        assert diag["escalated_after_attempts"] == 3

    def test_test_author_failure_at_threshold_escalates(self):
        gate = GateResult(
            passed=False,
            gate_name=GATE_NAME_TEST_SUITE_COLLECT,
            diagnostics=["collect failed"],
            diagnostic_kind="test_collect",
        )
        result = route(
            "gating",
            "gate_fail",
            gate_result=gate,
            attempt_number=3,
            attempt_threshold=3,
        )
        assert result.target_state == "cannot_proceed"
        assert result.diagnostic_kind == DiagnosticKind.CANNOT_PROCEED_SEAM
        diag = result.custom_fields_update["diagnostics"]
        assert diag["escalated_from_kind"] == "test_collect"

    def test_interface_architect_failure_never_escalates(self):
        gate = GateResult(
            passed=False,
            gate_name=GATE_NAME_INTERFACE_SPEC_SYNTAX,
            diagnostics=["SyntaxError"],
            diagnostic_kind="syntax",
        )
        result = route(
            "gating",
            "gate_fail",
            gate_result=gate,
            attempt_number=5,
            attempt_threshold=3,
        )
        assert result.target_state == "new"
        assert result.diagnostic_kind == DiagnosticKind.SYNTAX

    def test_escalation_preserves_original_diagnostics(self):
        gate = GateResult(
            passed=False,
            gate_name=GATE_NAME_IMPLEMENTATION_MYPY,
            diagnostics=["error: Incompatible return type"],
            diagnostic_kind="impl_mypy",
        )
        result = route(
            "gating",
            "gate_fail",
            gate_result=gate,
            attempt_number=3,
            attempt_threshold=3,
        )
        assert result.diagnostics == ["error: Incompatible return type"]
        diag = result.custom_fields_update["diagnostics"]
        assert diag["messages"] == ["error: Incompatible return type"]

    def test_above_threshold_also_escalates(self):
        gate = GateResult(
            passed=False,
            gate_name=GATE_NAME_IMPLEMENTATION_LINT,
            diagnostics=["lint error"],
            diagnostic_kind="impl_lint",
        )
        result = route(
            "gating",
            "gate_fail",
            gate_result=gate,
            attempt_number=5,
            attempt_threshold=3,
        )
        assert result.target_state == "cannot_proceed"
        assert result.diagnostic_kind == DiagnosticKind.CANNOT_PROCEED_SEAM


class TestDispatchCompleteness:
    def test_all_diagnostic_kinds_have_dispatch_entries(self):
        for kind in DiagnosticKind:
            assert kind in _PHASE2_DISPATCH, f"Missing dispatch for {kind}"

    def test_route_has_no_target_role_field(self):
        import dataclasses

        from factory.router import Route

        field_names = {f.name for f in dataclasses.fields(Route)}
        assert "target_role" not in field_names
