from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from factory.constants import (
    STATE_CANNOT_PROCEED,
    STATE_GATING,
    STATE_LOCKED,
    STATE_NEW,
    TRANSITION_CHANNEL_FAIL,
    TRANSITION_GATE_FAIL,
    TRANSITION_GATE_PASS,
)
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
    TEST_NO_ASSERTIONS = "test_no_assertions"
    IMPL_MYPY = "impl_mypy"
    IMPL_PYTEST = "impl_pytest"
    IMPL_LINT = "impl_lint"
    IMPL_IMPORT = "impl_import"
    CANNOT_PROCEED_SEAM = "cannot_proceed_seam"
    MISSING_DEPENDENCY = "missing_dependency"
    MISSING_ARTIFACT = "missing_artifact"
    TOOL_NOT_FOUND = "tool_not_found"
    CROSS_FAMILY_REVIEW = "cross_family_review"
    JURY = "jury"


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
    if gate_result.diagnostic_kind == "cross_family_review":
        return DiagnosticKind.CROSS_FAMILY_REVIEW
    if gate_result.diagnostic_kind == "jury":
        return DiagnosticKind.JURY
    return DiagnosticKind.GENERIC


@dataclass(frozen=True)
class Route:
    target_state: str
    diagnostics: list[str] = field(default_factory=list)
    custom_fields_update: dict = field(default_factory=dict)
    diagnostic_kind: DiagnosticKind = DiagnosticKind.GENERIC


_PHASE2_DISPATCH = {
    DiagnosticKind.SYNTAX: Route(
        target_state=STATE_NEW,
    ),
    DiagnosticKind.STUB: Route(
        target_state=STATE_NEW,
    ),
    DiagnosticKind.STRUCTURAL_SEMANTICS: Route(
        target_state=STATE_NEW,
    ),
    DiagnosticKind.FILE_EXISTS: Route(
        target_state=STATE_NEW,
    ),
    DiagnosticKind.NOT_EMPTY: Route(
        target_state=STATE_NEW,
    ),
    DiagnosticKind.CHANNEL_FAIL: Route(
        target_state=STATE_NEW,
    ),
    DiagnosticKind.CANNOT_PROCEED: Route(
        target_state=STATE_CANNOT_PROCEED,
    ),
    DiagnosticKind.UNKNOWN_TYPE: Route(
        target_state=STATE_NEW,
    ),
    DiagnosticKind.GENERIC: Route(
        target_state=STATE_NEW,
    ),
    DiagnosticKind.TEST_AC_BINDING: Route(
        target_state=STATE_NEW,
    ),
    DiagnosticKind.TEST_COLLECT: Route(
        target_state=STATE_NEW,
    ),
    DiagnosticKind.TEST_IMPORT_FORBIDDEN: Route(
        target_state=STATE_NEW,
    ),
    DiagnosticKind.TEST_NO_ASSERTIONS: Route(
        target_state=STATE_NEW,
    ),
    DiagnosticKind.IMPL_MYPY: Route(
        target_state=STATE_NEW,
    ),
    DiagnosticKind.IMPL_PYTEST: Route(
        target_state=STATE_NEW,
    ),
    DiagnosticKind.IMPL_LINT: Route(
        target_state=STATE_NEW,
    ),
    DiagnosticKind.IMPL_IMPORT: Route(
        target_state=STATE_NEW,
    ),
    DiagnosticKind.CANNOT_PROCEED_SEAM: Route(
        target_state=STATE_CANNOT_PROCEED,
    ),
    DiagnosticKind.MISSING_DEPENDENCY: Route(
        target_state=STATE_CANNOT_PROCEED,
    ),
    DiagnosticKind.MISSING_ARTIFACT: Route(
        target_state=STATE_NEW,
    ),
    DiagnosticKind.TOOL_NOT_FOUND: Route(
        target_state=STATE_CANNOT_PROCEED,
    ),
    DiagnosticKind.CROSS_FAMILY_REVIEW: Route(
        target_state=STATE_NEW,
    ),
    DiagnosticKind.JURY: Route(
        target_state=STATE_NEW,
    ),
}


# Worker-retryable failures: these kinds originate from non-deterministic channel
# output (mypy/pytest/lint/import errors, test binding/collect/import issues) and
# are eligible for escalation to cannot_proceed_seam after attempt_threshold retries.
# Deterministic gate failures (syntax, stub, structural_semantics, file_exists,
# not_empty, channel_fail, cannot_proceed, unknown_type) are NOT escalatable — they
# always route directly to the originating role for immediate correction.
_ESCALATABLE_KINDS = {
    DiagnosticKind.IMPL_MYPY,
    DiagnosticKind.IMPL_PYTEST,
    DiagnosticKind.IMPL_LINT,
    DiagnosticKind.IMPL_IMPORT,
    DiagnosticKind.TEST_AC_BINDING,
    DiagnosticKind.TEST_COLLECT,
    DiagnosticKind.TEST_IMPORT_FORBIDDEN,
    DiagnosticKind.CROSS_FAMILY_REVIEW,
    DiagnosticKind.JURY,
}


def route(
    current_state: str,
    transition: str,
    gate_result: GateResult | None = None,
    attempt_number: int = 0,
    attempt_threshold: int = 3,
) -> Route:
    if current_state == STATE_GATING and transition == TRANSITION_GATE_PASS:
        return Route(target_state=STATE_LOCKED)

    if current_state == STATE_GATING and transition == TRANSITION_GATE_FAIL:
        if gate_result is not None:
            kind = _classify_diagnostic(gate_result)
            base = _PHASE2_DISPATCH.get(kind, Route(target_state="new"))

            if kind in _ESCALATABLE_KINDS and attempt_number >= attempt_threshold:
                escalation = _PHASE2_DISPATCH[DiagnosticKind.CANNOT_PROCEED_SEAM]
                return Route(
                    target_state=escalation.target_state,
                    diagnostics=gate_result.diagnostics,
                    diagnostic_kind=DiagnosticKind.CANNOT_PROCEED_SEAM,
                    custom_fields_update={
                        "diagnostics": {
                            "gate_name": gate_result.gate_name,
                            "passed": gate_result.passed,
                            "messages": gate_result.diagnostics,
                            "message": "; ".join(gate_result.diagnostics),
                            "diagnostic_kind": DiagnosticKind.CANNOT_PROCEED_SEAM.value,
                            "escalated_from_kind": kind.value,
                            "escalated_after_attempts": attempt_number,
                        }
                    },
                )

            return Route(
                target_state=base.target_state,
                diagnostics=gate_result.diagnostics,
                diagnostic_kind=kind,
                custom_fields_update={
                    "diagnostics": {
                        "gate_name": gate_result.gate_name,
                        "passed": gate_result.passed,
                        "messages": gate_result.diagnostics,
                        "message": "; ".join(gate_result.diagnostics),
                        "diagnostic_kind": kind.value,
                    }
                },
            )
        return Route(target_state=STATE_NEW, diagnostic_kind=DiagnosticKind.GENERIC)

    if current_state == STATE_NEW and transition == TRANSITION_CHANNEL_FAIL:
        return Route(
            target_state=STATE_NEW,
            diagnostic_kind=DiagnosticKind.CHANNEL_FAIL,
        )

    raise ValueError(f"No route for state={current_state}, transition={transition}")
