from __future__ import annotations

from dataclasses import dataclass, field

from factory.gate import GateResult


@dataclass(frozen=True)
class Route:
    target_state: str
    target_role: str | None = None
    diagnostics: list[str] = field(default_factory=list)
    custom_fields_update: dict = field(default_factory=dict)


_PHASE1_ROUTING = {
    ("gating", "gate_pass"): Route(target_state="locked"),
    ("gating", "gate_fail"): Route(
        target_state="new",
        custom_fields_update={"diagnostics": []},
    ),
}


def route(
    current_state: str,
    transition: str,
    gate_result: GateResult | None = None,
    work_item_type: str = "interface_spec",
) -> Route:
    if current_state == "gating" and transition == "gate_fail" and gate_result is not None:
        return Route(
            target_state="new",
            diagnostics=gate_result.diagnostics,
            custom_fields_update={
                "diagnostics": {
                    "gate_name": gate_result.gate_name,
                    "passed": gate_result.passed,
                    "message": "; ".join(gate_result.diagnostics),
                }
            },
        )
    key = (current_state, transition)
    if key in _PHASE1_ROUTING:
        return _PHASE1_ROUTING[key]
    raise ValueError(f"No route for state={current_state}, transition={transition}")
