from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from factory.constants import (
    STATE_CANNOT_PROCEED,
    STATE_GATING,
    STATE_LOCKED,
    STATE_NEW,
    TRANSITION_CHANNEL_FAIL,
    TRANSITION_GATE_FAIL,
    TRANSITION_GATE_PASS,
    WORK_ITEM_TYPE_IMPLEMENTATION,
    WORK_ITEM_TYPE_TEST_SUITE,
    DiagnosticKind,
)
from factory.gate import GateResult

# DiagnosticKind is re-exported from constants for backward compatibility.
# All new code should import from factory.constants directly.


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
    diagnostics: list[str] = field(default_factory=list)
    custom_fields_update: dict = field(default_factory=dict)
    diagnostic_kind: DiagnosticKind = DiagnosticKind.GENERIC
    create_upstream_revision: bool = False
    upstream_type: str | None = None
    upstream_context_key: str | None = None


@dataclass(frozen=True)
class RouteContext:
    current_state: str
    transition: str
    gate_result: GateResult | None
    attempt_number: int
    attempt_threshold: int
    kind: DiagnosticKind | None = None


KIND_DISPATCH = {
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
        custom_fields_update={"review_feedback_pending": True},
    ),
    DiagnosticKind.REVIEW_MALFORMED: Route(
        target_state=STATE_NEW,
    ),
    DiagnosticKind.REVIEW_FOUND_DEFECT: Route(
        target_state=STATE_NEW,
        custom_fields_update={"review_feedback_pending": True},
        create_upstream_revision=True,
        upstream_type=WORK_ITEM_TYPE_IMPLEMENTATION,
        upstream_context_key="review_feedback",
    ),
    DiagnosticKind.JURY: Route(
        target_state=STATE_NEW,
    ),
    DiagnosticKind.INTEGRATION_IMPORT: Route(
        target_state=STATE_NEW,
    ),
    DiagnosticKind.INTEGRATION_UNSAFE_PATH: Route(
        target_state=STATE_NEW,
    ),
    DiagnosticKind.INTEGRATION_MYPY: Route(
        target_state=STATE_NEW,
    ),
    DiagnosticKind.INTEGRATION_PYTEST: Route(
        target_state=STATE_NEW,
    ),
    DiagnosticKind.OUTCOME_E2E: Route(
        target_state=STATE_NEW,
    ),
    DiagnosticKind.ARTIFACT_OVERSIZED: Route(
        target_state=STATE_NEW,
    ),
    DiagnosticKind.MUTATION_UNCAUGHT: Route(
        target_state=STATE_NEW,
        custom_fields_update={"review_feedback_pending": True},
        create_upstream_revision=True,
        upstream_type=WORK_ITEM_TYPE_TEST_SUITE,
        upstream_context_key="review_feedback",
    ),
}


ESCALATABLE_KINDS = {
    DiagnosticKind.IMPL_MYPY,
    DiagnosticKind.IMPL_PYTEST,
    DiagnosticKind.IMPL_LINT,
    DiagnosticKind.IMPL_IMPORT,
    DiagnosticKind.TEST_AC_BINDING,
    DiagnosticKind.TEST_COLLECT,
    DiagnosticKind.TEST_IMPORT_FORBIDDEN,
    DiagnosticKind.CROSS_FAMILY_REVIEW,
    DiagnosticKind.REVIEW_MALFORMED,
    DiagnosticKind.JURY,
    DiagnosticKind.INTEGRATION_IMPORT,
    DiagnosticKind.INTEGRATION_MYPY,
    DiagnosticKind.INTEGRATION_PYTEST,
    DiagnosticKind.OUTCOME_E2E,
    DiagnosticKind.MUTATION_UNCAUGHT,
}

# Backward-compatible aliases (BC-218: made public; private names deprecated)
_KIND_DISPATCH = KIND_DISPATCH
_ESCALATABLE_KINDS = ESCALATABLE_KINDS

# Worker-retryable failures: these kinds originate from non-deterministic channel
# output (mypy/pytest/lint/import errors, test binding/collect/import issues) and
# are eligible for escalation to cannot_proceed_seam after attempt_threshold retries.
# Deterministic gate failures (syntax, stub, structural_semantics, file_exists,
# not_empty, channel_fail, cannot_proceed, unknown_type) are NOT escalatable — they
# always route directly to the originating role for immediate correction.
#
# REVIEW_FOUND_DEFECT is NOT in this set because it routes upstream to the implementer
# or test_author for revision, not to retry the reviewer.
# CROSS_FAMILY_REVIEW (legacy string-diagnostic from Phase 4) IS still escalatable
# because it lacks structured findings — we cannot distinguish malformed from defect.
# OUTCOME_E2E is NOT in this set because it routes directly to cannot_proceed
# when a routing_hint is present (BC-158), or retries at attempt_threshold otherwise.


class RouteHandler(ABC):
    @abstractmethod
    def can_handle(self, ctx: RouteContext) -> bool: ...

    @abstractmethod
    def build_route(self, ctx: RouteContext) -> Route: ...


class RoutingHintHandler(RouteHandler):
    def can_handle(self, ctx: RouteContext) -> bool:
        return (
            ctx.kind == DiagnosticKind.OUTCOME_E2E
            and ctx.gate_result is not None
            and ctx.gate_result.routing_hint is not None
        )

    def build_route(self, ctx: RouteContext) -> Route:
        gr = ctx.gate_result
        return Route(
            target_state=STATE_CANNOT_PROCEED,
            diagnostics=gr.diagnostics,
            diagnostic_kind=DiagnosticKind.OUTCOME_E2E,
            custom_fields_update={
                "diagnostics": {
                    "gate_name": gr.gate_name,
                    "passed": gr.passed,
                    "messages": gr.diagnostics,
                    "message": "; ".join(gr.diagnostics),
                    "diagnostic_kind": DiagnosticKind.OUTCOME_E2E.value,
                    "routing_hint": gr.routing_hint,
                }
            },
        )


class EscalationHandler(RouteHandler):
    def can_handle(self, ctx: RouteContext) -> bool:
        return (
            ctx.kind is not None
            and ctx.kind in ESCALATABLE_KINDS
            and ctx.attempt_number >= ctx.attempt_threshold
        )

    def build_route(self, ctx: RouteContext) -> Route:
        gr = ctx.gate_result
        return Route(
            target_state=STATE_CANNOT_PROCEED,
            diagnostics=gr.diagnostics if gr else [],
            diagnostic_kind=DiagnosticKind.CANNOT_PROCEED_SEAM,
            custom_fields_update={
                "diagnostics": {
                    "gate_name": gr.gate_name if gr else "",
                    "passed": gr.passed if gr else False,
                    "messages": gr.diagnostics if gr else [],
                    "message": "; ".join(gr.diagnostics) if gr else "",
                    "diagnostic_kind": DiagnosticKind.CANNOT_PROCEED_SEAM.value,
                    "escalated_from_kind": ctx.kind.value if ctx.kind else "",
                    "escalated_after_attempts": ctx.attempt_number,
                }
            },
        )


class DispatchHandler(RouteHandler):
    def can_handle(self, ctx: RouteContext) -> bool:
        return ctx.kind is not None and ctx.kind in KIND_DISPATCH

    def build_route(self, ctx: RouteContext) -> Route:
        gr = ctx.gate_result
        base = KIND_DISPATCH.get(ctx.kind, Route(target_state=STATE_NEW))
        return Route(
            target_state=base.target_state,
            diagnostics=gr.diagnostics if gr else [],
            diagnostic_kind=ctx.kind,
            custom_fields_update={
                **base.custom_fields_update,
                **{
                    "diagnostics": {
                        "gate_name": gr.gate_name if gr else "",
                        "passed": gr.passed if gr else False,
                        "messages": gr.diagnostics if gr else [],
                        "message": "; ".join(gr.diagnostics) if gr else "",
                        "diagnostic_kind": ctx.kind.value if ctx.kind else "",
                    }
                },
            },
            create_upstream_revision=base.create_upstream_revision,
            upstream_type=base.upstream_type,
            upstream_context_key=base.upstream_context_key,
        )


_HANDLERS: list[RouteHandler] = [
    RoutingHintHandler(),
    EscalationHandler(),
    DispatchHandler(),
]


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
        kind = _classify_diagnostic(gate_result) if gate_result else None
        ctx = RouteContext(
            current_state=current_state,
            transition=transition,
            gate_result=gate_result,
            attempt_number=attempt_number,
            attempt_threshold=attempt_threshold,
            kind=kind,
        )
        for handler in _HANDLERS:
            if handler.can_handle(ctx):
                return handler.build_route(ctx)
        return Route(target_state=STATE_NEW, diagnostic_kind=DiagnosticKind.GENERIC)

    if current_state == STATE_NEW and transition == TRANSITION_CHANNEL_FAIL:
        return Route(
            target_state=STATE_NEW,
            diagnostic_kind=DiagnosticKind.CHANNEL_FAIL,
        )

    raise ValueError(f"No route for state={current_state}, transition={transition}")
