from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from factory.gate import GateResult


class DiagnosticKind(StrEnum):
    SYNTAX = "syntax"
    STUB = "stub"
    STRUCTURAL_SEMANTICS = "structural_semantics"
    FILE_EXISTS = "file_exists"
    NOT_EMPTY = "not_empty"
    CHANNEL_FAIL = "channel_fail"
    CANNOT_PROCEED = "cannot_proceed"
    UNKNOWN_TYPE = "unknown_type"
    GENERIC = "generic"
    TEST_AC_BINDING = "test_ac_binding"
    TEST_COLLECT = "test_collect"
    TEST_IMPORT_FORBIDDEN = "test_import_forbidden"
    IMPL_MYPY = "impl_mypy"
    IMPL_PYTEST = "impl_pytest"
    IMPL_LINT = "impl_lint"
    IMPL_IMPORT = "impl_import"


KIND_TO_ROLE: dict[DiagnosticKind, str] = {
    DiagnosticKind.SYNTAX: "interface_architect",
    DiagnosticKind.STUB: "interface_architect",
    DiagnosticKind.STRUCTURAL_SEMANTICS: "interface_architect",
    DiagnosticKind.FILE_EXISTS: "interface_architect",
    DiagnosticKind.NOT_EMPTY: "interface_architect",
    DiagnosticKind.CHANNEL_FAIL: "interface_architect",
    DiagnosticKind.CANNOT_PROCEED: "interface_architect",
    DiagnosticKind.UNKNOWN_TYPE: "interface_architect",
    DiagnosticKind.GENERIC: "interface_architect",
}


def _classify_diagnostic(gate_result: GateResult) -> DiagnosticKind:
    if gate_result.diagnostic_kind:
        for kind in DiagnosticKind:
            if kind.value == gate_result.diagnostic_kind:
                return kind
    name = gate_result.gate_name
    if "syntax" in name:
        return DiagnosticKind.SYNTAX
    if "stub" in name:
        return DiagnosticKind.STUB
    if "structural_semantics" in name:
        return DiagnosticKind.STRUCTURAL_SEMANTICS
    if "file_exists" in name:
        return DiagnosticKind.FILE_EXISTS
    if "not_empty" in name:
        return DiagnosticKind.NOT_EMPTY
    if "channel_fail" in name:
        return DiagnosticKind.CHANNEL_FAIL
    if "cannot_proceed" in name:
        return DiagnosticKind.CANNOT_PROCEED
    if "unknown_type" in name:
        return DiagnosticKind.UNKNOWN_TYPE
    return DiagnosticKind.GENERIC


@dataclass(frozen=True)
class Route:
    target_state: str
    target_role: str | None = None
    diagnostics: list[str] = field(default_factory=list)
    custom_fields_update: dict = field(default_factory=dict)
    diagnostic_kind: DiagnosticKind = DiagnosticKind.GENERIC


_PHASE2_DISPATCH = {
    DiagnosticKind.SYNTAX: Route(
        target_state="new",
        target_role="interface_architect",
    ),
    DiagnosticKind.STUB: Route(
        target_state="new",
        target_role="interface_architect",
    ),
    DiagnosticKind.STRUCTURAL_SEMANTICS: Route(
        target_state="new",
        target_role="interface_architect",
    ),
    DiagnosticKind.FILE_EXISTS: Route(
        target_state="new",
        target_role="interface_architect",
    ),
    DiagnosticKind.NOT_EMPTY: Route(
        target_state="new",
        target_role="interface_architect",
    ),
    DiagnosticKind.CHANNEL_FAIL: Route(
        target_state="new",
        target_role="interface_architect",
    ),
    DiagnosticKind.CANNOT_PROCEED: Route(
        target_state="cannot_proceed",
        target_role="interface_architect",
    ),
    DiagnosticKind.UNKNOWN_TYPE: Route(
        target_state="new",
        target_role="interface_architect",
    ),
    DiagnosticKind.GENERIC: Route(
        target_state="new",
        target_role="interface_architect",
    ),
    DiagnosticKind.TEST_AC_BINDING: Route(
        target_state="new",
        target_role="test_author",
    ),
    DiagnosticKind.TEST_COLLECT: Route(
        target_state="new",
        target_role="test_author",
    ),
    DiagnosticKind.TEST_IMPORT_FORBIDDEN: Route(
        target_state="new",
        target_role="test_author",
    ),
    DiagnosticKind.IMPL_MYPY: Route(
        target_state="new",
        target_role="implementer",
    ),
    DiagnosticKind.IMPL_PYTEST: Route(
        target_state="new",
        target_role="implementer",
    ),
    DiagnosticKind.IMPL_LINT: Route(
        target_state="new",
        target_role="implementer",
    ),
    DiagnosticKind.IMPL_IMPORT: Route(
        target_state="new",
        target_role="implementer",
    ),
}


def route(
    current_state: str,
    transition: str,
    gate_result: GateResult | None = None,
) -> Route:
    if current_state == "gating" and transition == "gate_pass":
        return Route(target_state="locked")

    if current_state == "gating" and transition == "gate_fail":
        if gate_result is not None:
            kind = _classify_diagnostic(gate_result)
            base = _PHASE2_DISPATCH.get(kind, Route(target_state="new"))
            return Route(
                target_state=base.target_state,
                target_role=base.target_role,
                diagnostics=gate_result.diagnostics,
                diagnostic_kind=kind,
                custom_fields_update={
                    "diagnostics": {
                        "gate_name": gate_result.gate_name,
                        "passed": gate_result.passed,
                        "messages": gate_result.diagnostics,
                        "message": "; ".join(gate_result.diagnostics),
                        "diagnostic_kind": kind.value,
                        "target_role": base.target_role,
                    }
                },
            )
        return Route(target_state="new", diagnostic_kind=DiagnosticKind.GENERIC)

    if current_state == "new" and transition == "channel_fail":
        return Route(
            target_state="new",
            target_role="interface_architect",
            diagnostic_kind=DiagnosticKind.CHANNEL_FAIL,
        )

    raise ValueError(f"No route for state={current_state}, transition={transition}")
