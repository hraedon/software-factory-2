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
from factory.router import Route
from factory.runtime import PipelineRuntime


def _make_runtime():
    sub = MagicMock()
    config = FactoryConfig.phase5()
    runtime = PipelineRuntime(sub=sub, config=config)
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
