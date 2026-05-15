from __future__ import annotations

import pytest

from factory.constants import (
    GATE_NAME_CROSS_FAMILY_REVIEW,
    GATE_NAME_INTERFACE_SPEC_FILE_EXISTS,
    GATE_NAME_INTERFACE_SPEC_NOT_EMPTY,
    GATE_NAME_INTERFACE_SPEC_STRUCTURAL_SEMANTICS,
    GATE_NAME_INTERFACE_SPEC_STUB,
    GATE_NAME_INTERFACE_SPEC_SYNTAX,
    GATE_NAME_JURY_DISAGREE,
)
from factory.gate import GateResult
from factory.router import DiagnosticKind, _classify_diagnostic, route


class TestRouterPhase1:
    def test_gate_pass_to_locked(self):
        result = route("gating", "gate_pass")
        assert result.target_state == "locked"

    def test_gate_fail_syntax_classified_correctly(self):
        gate = GateResult(
            passed=False,
            gate_name=GATE_NAME_INTERFACE_SPEC_SYNTAX,
            diagnostics=["SyntaxError at line 5"],
            diagnostic_kind="syntax",
        )
        result = route("gating", "gate_fail", gate_result=gate)
        assert result.target_state == "new"
        assert result.diagnostic_kind == DiagnosticKind.SYNTAX
        assert "syntax" in result.custom_fields_update["diagnostics"]["diagnostic_kind"]

    def test_gate_fail_structural_semantics_classified(self):
        gate = GateResult(
            passed=False,
            gate_name=GATE_NAME_INTERFACE_SPEC_STRUCTURAL_SEMANTICS,
            diagnostics=["AC 'AC-02' not in any function/class docstring"],
            diagnostic_kind="structural_semantics",
        )
        result = route("gating", "gate_fail", gate_result=gate)
        assert result.target_state == "new"
        assert result.diagnostic_kind == DiagnosticKind.STRUCTURAL_SEMANTICS

    def test_gate_fail_with_diagnostics_in_custom_fields(self):
        gate = GateResult(
            passed=False,
            gate_name=GATE_NAME_INTERFACE_SPEC_SYNTAX,
            diagnostics=["SyntaxError at line 5"],
            diagnostic_kind="syntax",
        )
        result = route("gating", "gate_fail", gate_result=gate)
        assert result.diagnostics == ["SyntaxError at line 5"]
        assert (
            result.custom_fields_update["diagnostics"]["gate_name"]
            == GATE_NAME_INTERFACE_SPEC_SYNTAX
        )
        assert result.custom_fields_update["diagnostics"]["messages"] == ["SyntaxError at line 5"]
        assert result.custom_fields_update["diagnostics"]["message"] == "SyntaxError at line 5"

    def test_gate_fail_without_gate_result(self):
        result = route("gating", "gate_fail")
        assert result.target_state == "new"

    def test_unknown_transition_raises(self):
        with pytest.raises(ValueError, match="No route"):
            route("new", "unknown_transition")

    def test_channel_fail_route(self):
        result = route("new", "channel_fail")
        assert result.target_state == "new"
        assert result.diagnostic_kind == DiagnosticKind.CHANNEL_FAIL


class TestDiagnosticClassification:
    def test_syntax_parse(self):
        gate = GateResult(
            passed=False,
            gate_name=GATE_NAME_INTERFACE_SPEC_SYNTAX,
            diagnostics=["bad"],
            diagnostic_kind="syntax",
        )
        assert _classify_diagnostic(gate) == DiagnosticKind.SYNTAX

    def test_stub_parse(self):
        gate = GateResult(
            passed=False,
            gate_name=GATE_NAME_INTERFACE_SPEC_STUB,
            diagnostics=["bad"],
            diagnostic_kind="stub",
        )
        assert _classify_diagnostic(gate) == DiagnosticKind.STUB

    def test_structural_semantics_parse(self):
        gate = GateResult(
            passed=False,
            gate_name=GATE_NAME_INTERFACE_SPEC_STRUCTURAL_SEMANTICS,
            diagnostics=["bad"],
            diagnostic_kind="structural_semantics",
        )
        assert _classify_diagnostic(gate) == DiagnosticKind.STRUCTURAL_SEMANTICS

    def test_file_exists_parse(self):
        gate = GateResult(
            passed=False,
            gate_name=GATE_NAME_INTERFACE_SPEC_FILE_EXISTS,
            diagnostics=["bad"],
            diagnostic_kind="file_exists",
        )
        assert _classify_diagnostic(gate) == DiagnosticKind.FILE_EXISTS

    def test_not_empty_parse(self):
        gate = GateResult(
            passed=False,
            gate_name=GATE_NAME_INTERFACE_SPEC_NOT_EMPTY,
            diagnostics=["bad"],
            diagnostic_kind="not_empty",
        )
        assert _classify_diagnostic(gate) == DiagnosticKind.NOT_EMPTY

    def test_generic_fallback(self):
        gate = GateResult(
            passed=False,
            gate_name="some_unknown_gate",
            diagnostics=["bad"],
        )
        assert _classify_diagnostic(gate) == DiagnosticKind.GENERIC

    def test_cross_family_review_parse(self):
        gate = GateResult(
            passed=False,
            gate_name=GATE_NAME_CROSS_FAMILY_REVIEW,
            diagnostics=["Review did not pass"],
            diagnostic_kind="cross_family_review",
        )
        assert _classify_diagnostic(gate) == DiagnosticKind.CROSS_FAMILY_REVIEW

    def test_jury_parse(self):
        gate = GateResult(
            passed=False,
            gate_name=GATE_NAME_JURY_DISAGREE,
            diagnostics=["Jury quorum not met"],
            diagnostic_kind="jury",
        )
        assert _classify_diagnostic(gate) == DiagnosticKind.JURY


class TestBC158OutcomeRoutingHint:
    def test_outcome_e2e_with_routing_hint_routes_to_cannot_proceed(self):
        gate = GateResult(
            passed=False,
            gate_name="outcome_e2e",
            diagnostics=["Outcome verification failed"],
            diagnostic_kind="outcome_e2e",
            routing_hint={"work_item_type": "implementation", "reason": "stub impl"},
        )
        result = route("gating", "gate_fail", gate_result=gate)
        assert result.target_state == "cannot_proceed"
        assert result.diagnostic_kind == DiagnosticKind.OUTCOME_E2E
        assert result.custom_fields_update["diagnostics"]["routing_hint"] == {
            "work_item_type": "implementation",
            "reason": "stub impl",
        }

    def test_outcome_e2e_without_routing_hint_routes_to_new(self):
        gate = GateResult(
            passed=False,
            gate_name="outcome_e2e",
            diagnostics=["Outcome verification failed"],
            diagnostic_kind="outcome_e2e",
        )
        result = route("gating", "gate_fail", gate_result=gate)
        assert result.target_state == "new"

    def test_outcome_e2e_without_routing_hint_at_threshold(self):
        gate = GateResult(
            passed=False,
            gate_name="outcome_e2e",
            diagnostics=["Outcome verification failed"],
            diagnostic_kind="outcome_e2e",
        )
        result = route(
            "gating",
            "gate_fail",
            gate_result=gate,
            attempt_number=3,
            attempt_threshold=3,
        )
        assert result.target_state == "cannot_proceed"


class TestRFC025UpstreamRouting:
    def test_review_found_defect_has_upstream_fields(self):
        gate = GateResult(
            passed=False,
            gate_name=GATE_NAME_CROSS_FAMILY_REVIEW,
            diagnostics=["Impl fails on edge case"],
            diagnostic_kind="review_found_defect",
        )
        result = route("gating", "gate_fail", gate_result=gate)
        assert result.target_state == "new"
        assert result.create_upstream_revision is True
        assert result.upstream_type == "implementation"
        assert result.upstream_context_key == "review_feedback"

    def test_syntax_error_no_upstream(self):
        gate = GateResult(
            passed=False,
            gate_name=GATE_NAME_INTERFACE_SPEC_SYNTAX,
            diagnostics=["Syntax error"],
            diagnostic_kind="syntax",
        )
        result = route("gating", "gate_fail", gate_result=gate)
        assert result.create_upstream_revision is False
        assert result.upstream_type is None

    def test_impl_pytest_no_upstream(self):
        gate = GateResult(
            passed=False,
            gate_name="implementation_pytest",
            diagnostics=["test failed"],
            diagnostic_kind="impl_pytest",
        )
        result = route("gating", "gate_fail", gate_result=gate)
        assert result.create_upstream_revision is False

    def test_review_malformed_no_upstream(self):
        gate = GateResult(
            passed=False,
            gate_name=GATE_NAME_CROSS_FAMILY_REVIEW,
            diagnostics=["JSON parse error"],
            diagnostic_kind="review_malformed",
        )
        result = route("gating", "gate_fail", gate_result=gate)
        assert result.create_upstream_revision is False
