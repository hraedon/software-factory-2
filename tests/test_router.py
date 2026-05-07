from __future__ import annotations

import pytest

from factory.gate import GateResult
from factory.router import route


class TestRouterPhase1:
    def test_gate_pass_to_locked(self):
        result = route("gating", "gate_pass")
        assert result.target_state == "locked"

    def test_gate_fail_to_new_with_diagnostics(self):
        gate = GateResult(
            passed=False,
            gate_name="interface_spec_syntax",
            diagnostics=["SyntaxError at line 5"],
        )
        result = route("gating", "gate_fail", gate_result=gate)
        assert result.target_state == "new"
        assert result.diagnostics == ["SyntaxError at line 5"]
        assert result.custom_fields_update["diagnostics"]["gate_name"] == "interface_spec_syntax"
        assert result.custom_fields_update["diagnostics"]["messages"] == ["SyntaxError at line 5"]
        assert result.custom_fields_update["diagnostics"]["message"] == "SyntaxError at line 5"

    def test_gate_fail_without_gate_result(self):
        result = route("gating", "gate_fail")
        assert result.target_state == "new"
        assert isinstance(result.custom_fields_update["diagnostics"], dict)

    def test_unknown_transition_raises(self):
        with pytest.raises(ValueError, match="No route"):
            route("new", "unknown_transition")
