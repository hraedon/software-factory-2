from __future__ import annotations

import pytest

from factory.gate import GateResult
from factory.router import DiagnosticKind, _classify_diagnostic, route


class TestRouterPhase1:
    def test_gate_pass_to_locked(self):
        result = route("gating", "gate_pass")
        assert result.target_state == "locked"

    def test_gate_fail_syntax_classified_correctly(self):
        gate = GateResult(
            passed=False,
            gate_name="interface_spec_syntax",
            diagnostics=["SyntaxError at line 5"],
            diagnostic_kind="syntax",
        )
        result = route("gating", "gate_fail", gate_result=gate)
        assert result.target_state == "new"
        assert result.target_role == "interface_architect"
        assert result.diagnostic_kind == DiagnosticKind.SYNTAX
        assert "syntax" in result.custom_fields_update["diagnostics"]["diagnostic_kind"]

    def test_gate_fail_structural_semantics_classified(self):
        gate = GateResult(
            passed=False,
            gate_name="interface_spec_structural_semantics",
            diagnostics=["AC 'AC-02' not in any function/class docstring"],
            diagnostic_kind="structural_semantics",
        )
        result = route("gating", "gate_fail", gate_result=gate)
        assert result.target_state == "new"
        assert result.target_role == "interface_architect"
        assert result.diagnostic_kind == DiagnosticKind.STRUCTURAL_SEMANTICS

    def test_gate_fail_with_diagnostics_in_custom_fields(self):
        gate = GateResult(
            passed=False,
            gate_name="interface_spec_syntax",
            diagnostics=["SyntaxError at line 5"],
            diagnostic_kind="syntax",
        )
        result = route("gating", "gate_fail", gate_result=gate)
        assert result.diagnostics == ["SyntaxError at line 5"]
        assert result.custom_fields_update["diagnostics"]["gate_name"] == "interface_spec_syntax"
        assert result.custom_fields_update["diagnostics"]["messages"] == ["SyntaxError at line 5"]
        assert result.custom_fields_update["diagnostics"]["message"] == "SyntaxError at line 5"
        assert result.custom_fields_update["diagnostics"]["target_role"] == "interface_architect"

    def test_gate_fail_without_gate_result(self):
        result = route("gating", "gate_fail")
        assert result.target_state == "new"

    def test_unknown_transition_raises(self):
        with pytest.raises(ValueError, match="No route"):
            route("new", "unknown_transition")

    def test_channel_fail_route(self):
        result = route("new", "channel_fail")
        assert result.target_state == "new"
        assert result.target_role == "interface_architect"
        assert result.diagnostic_kind == DiagnosticKind.CHANNEL_FAIL


class TestDiagnosticClassification:
    def test_syntax_parse(self):
        gate = GateResult(
            passed=False,
            gate_name="interface_spec_syntax",
            diagnostics=["bad"],
            diagnostic_kind="syntax",
        )
        assert _classify_diagnostic(gate) == DiagnosticKind.SYNTAX

    def test_stub_parse(self):
        gate = GateResult(
            passed=False,
            gate_name="interface_spec_stub",
            diagnostics=["bad"],
            diagnostic_kind="stub",
        )
        assert _classify_diagnostic(gate) == DiagnosticKind.STUB

    def test_structural_semantics_parse(self):
        gate = GateResult(
            passed=False,
            gate_name="interface_spec_structural_semantics",
            diagnostics=["bad"],
            diagnostic_kind="structural_semantics",
        )
        assert _classify_diagnostic(gate) == DiagnosticKind.STRUCTURAL_SEMANTICS

    def test_file_exists_parse(self):
        gate = GateResult(
            passed=False,
            gate_name="interface_spec_file_exists",
            diagnostics=["bad"],
            diagnostic_kind="file_exists",
        )
        assert _classify_diagnostic(gate) == DiagnosticKind.FILE_EXISTS

    def test_not_empty_parse(self):
        gate = GateResult(
            passed=False,
            gate_name="interface_spec_not_empty",
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
