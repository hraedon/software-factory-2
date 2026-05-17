from __future__ import annotations

import uuid
from unittest.mock import MagicMock

from factory.config import FactoryConfig
from factory.constants import (
    CUSTOM_FIELD_AC_IDS,
    CUSTOM_FIELD_INTERFACE_REF,
    CUSTOM_FIELD_REVIEW_FINDINGS,
    CUSTOM_FIELD_REVIEW_REF,
    CUSTOM_FIELD_SPEC_SECTION,
    CUSTOM_FIELD_TEST_SUITE_REF,
    CUSTOM_FIELD_UPSTREAM_REVISION_OF,
    STATE_NEW,
    WORK_ITEM_TYPE_IMPLEMENTATION,
    WORK_ITEM_TYPE_JURY,
    WORK_ITEM_TYPE_REVIEW,
)
from factory.gate import GateResult
from factory.router import Route
from factory.runtime import PipelineRuntime


def _make_runtime():
    sub = MagicMock()
    config = FactoryConfig.phase5()
    runtime = PipelineRuntime(sub=sub, config=config)
    empty_page = MagicMock()
    empty_page.items = []
    sub.query_work_items.return_value = empty_page
    return runtime, sub


def _make_work_item(
    wi_type=WORK_ITEM_TYPE_REVIEW,
    custom_fields=None,
):
    wi = MagicMock()
    wi.work_item_id = uuid.uuid4()
    wi.work_item_type = wi_type
    wi.custom_fields = custom_fields or {
        CUSTOM_FIELD_SPEC_SECTION: "FR-01",
        CUSTOM_FIELD_AC_IDS: ["AC-01", "AC-02"],
    }
    return wi


class TestEnsureUpstreamRevision:
    def test_creates_upstream_implementation(self):
        runtime, sub = _make_runtime()
        source_wi = _make_work_item()
        route = Route(
            target_state=STATE_NEW,
            create_upstream_revision=True,
            upstream_type=WORK_ITEM_TYPE_IMPLEMENTATION,
            upstream_context_key="review_feedback",
            diagnostics=["Edge case failure on empty input"],
        )

        upstream_wi = MagicMock()
        upstream_wi.work_item_id = uuid.uuid4()
        sub.create_work_item.return_value = (upstream_wi, None)

        from factory.scheduler import ensure_upstream_revision

        ensure_upstream_revision(runtime, source_wi, route)

        sub.create_work_item.assert_called_once()
        call_kwargs = sub.create_work_item.call_args
        assert call_kwargs[1]["work_item_type"] == WORK_ITEM_TYPE_IMPLEMENTATION
        custom = call_kwargs[1]["custom_fields"]
        assert custom[CUSTOM_FIELD_UPSTREAM_REVISION_OF] == str(source_wi.work_item_id)
        assert CUSTOM_FIELD_REVIEW_FINDINGS in custom

    def test_no_revision_without_flag(self):
        runtime, sub = _make_runtime()
        source_wi = _make_work_item()
        route = Route(
            target_state=STATE_NEW,
            create_upstream_revision=False,
        )

        from factory.scheduler import ensure_upstream_revision

        ensure_upstream_revision(runtime, source_wi, route)

        sub.create_work_item.assert_not_called()

    def test_no_revision_without_upstream_type(self):
        runtime, sub = _make_runtime()
        source_wi = _make_work_item()
        route = Route(
            target_state=STATE_NEW,
            create_upstream_revision=True,
            upstream_type=None,
        )

        from factory.scheduler import ensure_upstream_revision

        ensure_upstream_revision(runtime, source_wi, route)

        sub.create_work_item.assert_not_called()

    def test_no_duplicate_revision(self):
        runtime, sub = _make_runtime()
        source_wi = _make_work_item(
            custom_fields={
                CUSTOM_FIELD_SPEC_SECTION: "FR-01",
                CUSTOM_FIELD_AC_IDS: ["AC-01"],
                CUSTOM_FIELD_UPSTREAM_REVISION_OF: str(uuid.uuid4()),
            }
        )
        route = Route(
            target_state=STATE_NEW,
            create_upstream_revision=True,
            upstream_type=WORK_ITEM_TYPE_IMPLEMENTATION,
        )

        from factory.scheduler import ensure_upstream_revision

        ensure_upstream_revision(runtime, source_wi, route)

        sub.create_work_item.assert_not_called()

    def test_propagates_spec_fields(self):
        runtime, sub = _make_runtime()
        source_wi = _make_work_item(
            custom_fields={
                CUSTOM_FIELD_SPEC_SECTION: "FR-03",
                CUSTOM_FIELD_AC_IDS: ["AC-05"],
            }
        )
        route = Route(
            target_state=STATE_NEW,
            create_upstream_revision=True,
            upstream_type=WORK_ITEM_TYPE_IMPLEMENTATION,
            upstream_context_key="review_feedback",
            diagnostics=["Bug in calculation"],
        )

        upstream_wi = MagicMock()
        sub.create_work_item.return_value = (upstream_wi, None)

        from factory.scheduler import ensure_upstream_revision

        ensure_upstream_revision(runtime, source_wi, route)

        call_kwargs = sub.create_work_item.call_args
        custom = call_kwargs[1]["custom_fields"]
        assert custom[CUSTOM_FIELD_SPEC_SECTION] == "FR-03"
        assert custom[CUSTOM_FIELD_AC_IDS] == ["AC-05"]

    def test_propagates_interface_and_test_suite_refs(self):
        runtime, sub = _make_runtime()
        upstream_id = str(uuid.uuid4())
        test_suite_id = str(uuid.uuid4())
        source_wi = _make_work_item(
            custom_fields={
                CUSTOM_FIELD_SPEC_SECTION: "FR-04",
                CUSTOM_FIELD_AC_IDS: ["AC-07"],
                CUSTOM_FIELD_INTERFACE_REF: upstream_id,
                CUSTOM_FIELD_TEST_SUITE_REF: test_suite_id,
            }
        )
        route = Route(
            target_state=STATE_NEW,
            create_upstream_revision=True,
            upstream_type=WORK_ITEM_TYPE_IMPLEMENTATION,
        )

        upstream_wi = MagicMock()
        sub.create_work_item.return_value = (upstream_wi, None)

        from factory.scheduler import ensure_upstream_revision

        ensure_upstream_revision(runtime, source_wi, route)

        call_kwargs = sub.create_work_item.call_args
        custom = call_kwargs[1]["custom_fields"]
        assert custom[CUSTOM_FIELD_INTERFACE_REF] == upstream_id
        assert custom[CUSTOM_FIELD_TEST_SUITE_REF] == test_suite_id

    def test_no_revision_when_no_role(self):
        runtime, sub = _make_runtime()
        runtime = PipelineRuntime(
            sub=sub,
            config=FactoryConfig(
                workflow_version=5,
                type_to_role=(("review", "cross_family_reviewer"),),
                roles=(MagicMock(),),
            ),
        )
        source_wi = _make_work_item()
        route = Route(
            target_state=STATE_NEW,
            create_upstream_revision=True,
            upstream_type=WORK_ITEM_TYPE_IMPLEMENTATION,
        )

        from factory.scheduler import ensure_upstream_revision

        ensure_upstream_revision(runtime, source_wi, route)

        sub.create_work_item.assert_not_called()

    def test_jury_source_resolves_refs_via_review_link(self):
        """When source is a jury, interface_ref and test_suite_ref must be
        resolved one hop away via review_ref → review.custom_fields."""
        runtime, sub = _make_runtime()

        review_id = str(uuid.uuid4())
        interface_id = str(uuid.uuid4())
        test_suite_id = str(uuid.uuid4())

        # Jury has only review_ref — no interface_ref / test_suite_ref
        jury_wi = _make_work_item(
            wi_type=WORK_ITEM_TYPE_JURY,
            custom_fields={
                CUSTOM_FIELD_SPEC_SECTION: "FR-05",
                CUSTOM_FIELD_AC_IDS: ["AC-10"],
                CUSTOM_FIELD_REVIEW_REF: review_id,
            },
        )

        # Mock the review returned by get_work_item — it carries both refs
        review_wi = MagicMock()
        review_wi.custom_fields = {
            CUSTOM_FIELD_INTERFACE_REF: interface_id,
            CUSTOM_FIELD_TEST_SUITE_REF: test_suite_id,
        }
        sub.get_work_item.return_value = review_wi

        upstream_wi = MagicMock()
        upstream_wi.work_item_id = uuid.uuid4()
        sub.create_work_item.return_value = (upstream_wi, None)

        route = Route(
            target_state=STATE_NEW,
            create_upstream_revision=True,
            upstream_type=WORK_ITEM_TYPE_IMPLEMENTATION,
            upstream_context_key="jury_feedback",
            diagnostics=["Jury found logic error"],
        )

        from factory.scheduler import ensure_upstream_revision

        ensure_upstream_revision(runtime, jury_wi, route)

        sub.create_work_item.assert_called_once()
        custom = sub.create_work_item.call_args[1]["custom_fields"]
        assert custom[CUSTOM_FIELD_INTERFACE_REF] == interface_id, (
            "interface_ref must be resolved from the linked review"
        )
        assert custom[CUSTOM_FIELD_TEST_SUITE_REF] == test_suite_id, (
            "test_suite_ref must be resolved from the linked review"
        )

    def test_jury_source_review_also_lacks_refs_no_crash(self):
        """Edge case: jury → review exists but review also has no interface_ref /
        test_suite_ref.  The code must not crash — it emits whatever it can resolve
        and lets substrate reject the payload in real use."""
        runtime, sub = _make_runtime()

        review_id = str(uuid.uuid4())

        jury_wi = _make_work_item(
            wi_type=WORK_ITEM_TYPE_JURY,
            custom_fields={
                CUSTOM_FIELD_SPEC_SECTION: "FR-06",
                CUSTOM_FIELD_AC_IDS: ["AC-11"],
                CUSTOM_FIELD_REVIEW_REF: review_id,
            },
        )

        # Review has neither ref
        review_wi = MagicMock()
        review_wi.custom_fields = {
            CUSTOM_FIELD_SPEC_SECTION: "FR-06",
        }
        sub.get_work_item.return_value = review_wi

        upstream_wi = MagicMock()
        upstream_wi.work_item_id = uuid.uuid4()
        sub.create_work_item.return_value = (upstream_wi, None)

        route = Route(
            target_state=STATE_NEW,
            create_upstream_revision=True,
            upstream_type=WORK_ITEM_TYPE_IMPLEMENTATION,
        )

        from factory.scheduler import ensure_upstream_revision

        # Must not raise — refs are simply absent from the payload
        ensure_upstream_revision(runtime, jury_wi, route)

        sub.create_work_item.assert_called_once()
        custom = sub.create_work_item.call_args[1]["custom_fields"]
        assert CUSTOM_FIELD_INTERFACE_REF not in custom
        assert CUSTOM_FIELD_TEST_SUITE_REF not in custom


class TestBC185RoutingFields:
    """AC-1, AC-2, AC-5: GateResult.routing_fields drives ensure_upstream_revision."""

    def test_routing_fields_review_findings_propagated_to_upstream(self):
        """AC-2 / AC-5: routing_fields['review_findings'] reaches the new impl revision."""
        runtime, sub = _make_runtime()
        source_wi = _make_work_item()

        structured = [{"ac_id": "AC-01", "kind": "impl", "severity": "block", "body": "stub"}]
        gate_result = GateResult(
            passed=False,
            gate_name="cross_family_review",
            diagnostic_kind="review_found_defect",
            routing_fields={CUSTOM_FIELD_REVIEW_FINDINGS: structured},
        )
        route = Route(
            target_state="new",
            create_upstream_revision=True,
            upstream_type=WORK_ITEM_TYPE_IMPLEMENTATION,
            upstream_context_key="review_feedback",
            diagnostics=["[block] AC-01 (impl): stub"],
        )

        upstream_wi = MagicMock()
        upstream_wi.work_item_id = uuid.uuid4()
        sub.create_work_item.return_value = (upstream_wi, None)

        from factory.scheduler import ensure_upstream_revision

        ensure_upstream_revision(runtime, source_wi, route, gate_result=gate_result)

        sub.create_work_item.assert_called_once()
        custom = sub.create_work_item.call_args[1]["custom_fields"]
        # Structured findings from routing_fields — not the text-only fallback
        assert custom[CUSTOM_FIELD_REVIEW_FINDINGS] == structured, (
            "routing_fields structured findings must reach the upstream revision"
        )

    def test_routing_fields_takes_precedence_over_route_diagnostics(self):
        """When routing_fields has review_findings, it wins over route.diagnostics fallback."""
        runtime, sub = _make_runtime()
        source_wi = _make_work_item()

        structured = [{"ac_id": "AC-02", "kind": "test", "severity": "block", "body": "missing"}]
        gate_result = GateResult(
            passed=False,
            gate_name="cross_family_review",
            routing_fields={CUSTOM_FIELD_REVIEW_FINDINGS: structured},
        )
        route = Route(
            target_state="new",
            create_upstream_revision=True,
            upstream_type=WORK_ITEM_TYPE_IMPLEMENTATION,
            upstream_context_key="review_feedback",
            diagnostics=["old text diagnostics"],
        )

        upstream_wi = MagicMock()
        upstream_wi.work_item_id = uuid.uuid4()
        sub.create_work_item.return_value = (upstream_wi, None)

        from factory.scheduler import ensure_upstream_revision

        ensure_upstream_revision(runtime, source_wi, route, gate_result=gate_result)

        custom = sub.create_work_item.call_args[1]["custom_fields"]
        # Must be the structured list, not a dict wrapping route.diagnostics
        assert custom[CUSTOM_FIELD_REVIEW_FINDINGS] == structured

    def test_fallback_to_route_diagnostics_when_no_routing_fields(self):
        """When gate_result has no routing_fields, fall back to route.diagnostics (legacy)."""
        runtime, sub = _make_runtime()
        source_wi = _make_work_item()

        gate_result = GateResult(
            passed=False,
            gate_name="cross_family_review",
            routing_fields={},  # empty — no structured findings
        )
        route = Route(
            target_state="new",
            create_upstream_revision=True,
            upstream_type=WORK_ITEM_TYPE_IMPLEMENTATION,
            upstream_context_key="review_feedback",
            diagnostics=["Fallback text finding"],
        )

        upstream_wi = MagicMock()
        upstream_wi.work_item_id = uuid.uuid4()
        sub.create_work_item.return_value = (upstream_wi, None)

        from factory.scheduler import ensure_upstream_revision

        ensure_upstream_revision(runtime, source_wi, route, gate_result=gate_result)

        custom = sub.create_work_item.call_args[1]["custom_fields"]
        assert CUSTOM_FIELD_REVIEW_FINDINGS in custom
        # Fallback uses the dict-wrapping format from route.diagnostics
        assert custom[CUSTOM_FIELD_REVIEW_FINDINGS]["findings"] == ["Fallback text finding"]

    def test_transition_fields_absent_from_routing_fields(self):
        """AC-1: transition_fields and routing_fields are separate; contents do not bleed."""
        gate_result = GateResult(
            passed=False,
            gate_name="cross_family_review",
            transition_fields={"some_transition_key": "val"},
            routing_fields={CUSTOM_FIELD_REVIEW_FINDINGS: [{"body": "defect"}]},
        )
        assert "some_transition_key" not in gate_result.routing_fields
        assert CUSTOM_FIELD_REVIEW_FINDINGS not in gate_result.transition_fields
