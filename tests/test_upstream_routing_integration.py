"""Integration tests for ensure_upstream_revision against a real regista backend.

Backend choice: InMemoryRegista — it enforces the same JSON-schema validation
as Postgres (same Python code path) without requiring a live DB.  The three
BC-145 bugs (missing test_suite_ref propagation, undeclared upstream_revision_of /
review_findings fields, upstream_revision_of type mismatch) would all have been
caught by these tests because InMemoryRegista rejects schema-invalid payloads
at create_work_item time, exactly as the real backend does.

The existing mocked tests in test_upstream_routing.py are NOT replaced — they
remain cheap branch-coverage for the Python logic.
"""

from __future__ import annotations

import pytest
from regista.testing import InMemoryRegista

from factory.config import FactoryConfig
from factory.constants import (
    ACTOR_ID_SCHEDULER,
    ACTOR_KIND_AGENT,
    CUSTOM_FIELD_AC_IDS,
    CUSTOM_FIELD_INTERFACE_REF,
    CUSTOM_FIELD_REVIEW_FINDINGS,
    CUSTOM_FIELD_SPEC_SECTION,
    CUSTOM_FIELD_TEST_SUITE_REF,
    CUSTOM_FIELD_UPSTREAM_REVISION_OF,
    ROLE_CROSS_FAMILY_REVIEWER,
    ROLE_FRONTIER_JUDGE,
    ROLE_IMPLEMENTER,
    ROLE_MECHANICAL_GATE,
    STATE_NEW,
    WORK_ITEM_TYPE_IMPLEMENTATION,
    WORK_ITEM_TYPE_INTERFACE_SPEC,
    WORK_ITEM_TYPE_JURY,
    WORK_ITEM_TYPE_REVIEW,
    WORK_ITEM_TYPE_TEST_SUITE,
)
from factory.router import Route
from factory.runtime import PipelineRuntime
from factory.scheduler import ensure_upstream_revision

WORKFLOW_V5_PATH = str(
    __import__("pathlib").Path(__file__).parent.parent / "workflows" / "phase5.yaml"
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def p5_sub():
    """Fresh InMemoryRegista registered with phase5 workflow."""
    sub = InMemoryRegista()
    sub.register_workflow_file(WORKFLOW_V5_PATH)
    # Register all roles that create_work_item will use
    sub.register_actor_role(ACTOR_ID_SCHEDULER, ROLE_IMPLEMENTER)
    sub.register_actor_role("factory-arch", ROLE_CROSS_FAMILY_REVIEWER)
    sub.register_actor_role("factory-judge", ROLE_FRONTIER_JUDGE)
    sub.register_actor_role("factory-gate", ROLE_MECHANICAL_GATE)
    yield sub
    sub.close()


@pytest.fixture()
def p5_config(tmp_path):
    return FactoryConfig.phase5(workspace_root=tmp_path / "work")


@pytest.fixture()
def runtime(p5_sub, p5_config):
    return PipelineRuntime(sub=p5_sub, config=p5_config)


def _create_interface_spec(sub) -> object:
    """Create a minimal interface_spec work item (required by downstream refs)."""
    sub.register_actor_role("factory-arch-iface", "interface_architect")
    wi, _ = sub.create_work_item(
        workflow_name="software_factory",
        work_item_type=WORK_ITEM_TYPE_INTERFACE_SPEC,
        actor_id="factory-arch-iface",
        actor_kind=ACTOR_KIND_AGENT,
        actor_metadata={"role": "interface_architect"},
        custom_fields={
            CUSTOM_FIELD_SPEC_SECTION: "FR-01",
            CUSTOM_FIELD_AC_IDS: ["AC-01"],
        },
    )
    return wi


def _create_test_suite(sub, interface_wi) -> object:
    """Create a minimal test_suite work item."""
    sub.register_actor_role("factory-tester", "test_author")
    wi, _ = sub.create_work_item(
        workflow_name="software_factory",
        work_item_type=WORK_ITEM_TYPE_TEST_SUITE,
        actor_id="factory-tester",
        actor_kind=ACTOR_KIND_AGENT,
        actor_metadata={"role": "test_author"},
        custom_fields={
            CUSTOM_FIELD_SPEC_SECTION: "FR-01",
            CUSTOM_FIELD_AC_IDS: ["AC-01"],
            CUSTOM_FIELD_INTERFACE_REF: str(interface_wi.work_item_id),
        },
    )
    return wi


def _create_review_wi(sub, interface_wi, test_suite_wi) -> object:
    """Create a review work item with all required and routing-relevant custom fields."""
    sub.register_actor_role("factory-reviewer", ROLE_CROSS_FAMILY_REVIEWER)
    # review requires: spec_section, ac_ids, interface_ref, test_suite_ref, implementation_ref
    # We need an implementation to hang implementation_ref on.
    impl_wi, _ = sub.create_work_item(
        workflow_name="software_factory",
        work_item_type=WORK_ITEM_TYPE_IMPLEMENTATION,
        actor_id=ACTOR_ID_SCHEDULER,
        actor_kind=ACTOR_KIND_AGENT,
        actor_metadata={"role": ROLE_IMPLEMENTER},
        custom_fields={
            CUSTOM_FIELD_SPEC_SECTION: "FR-01",
            CUSTOM_FIELD_AC_IDS: ["AC-01"],
            CUSTOM_FIELD_INTERFACE_REF: str(interface_wi.work_item_id),
            CUSTOM_FIELD_TEST_SUITE_REF: str(test_suite_wi.work_item_id),
        },
    )
    review_wi, _ = sub.create_work_item(
        workflow_name="software_factory",
        work_item_type=WORK_ITEM_TYPE_REVIEW,
        actor_id="factory-reviewer",
        actor_kind=ACTOR_KIND_AGENT,
        actor_metadata={"role": ROLE_CROSS_FAMILY_REVIEWER},
        custom_fields={
            CUSTOM_FIELD_SPEC_SECTION: "FR-01",
            CUSTOM_FIELD_AC_IDS: ["AC-01"],
            CUSTOM_FIELD_INTERFACE_REF: str(interface_wi.work_item_id),
            CUSTOM_FIELD_TEST_SUITE_REF: str(test_suite_wi.work_item_id),
            "implementation_ref": str(impl_wi.work_item_id),
        },
    )
    return review_wi


def _create_jury_wi(sub, review_wi) -> object:
    """Create a jury work item hanging off a review.

    The jury work_item_type (phase4.yaml) only declares: spec_section, ac_ids,
    module_name, review_ref, dependency_refs, artifact_path, artifact_hash,
    diagnostics.  It does NOT have interface_ref / test_suite_ref, so we do not
    pass those here — the scheduler picks them up from review_wi when propagating.
    """
    sub.register_actor_role("factory-judge", ROLE_FRONTIER_JUDGE)
    jury_wi, _ = sub.create_work_item(
        workflow_name="software_factory",
        work_item_type=WORK_ITEM_TYPE_JURY,
        actor_id="factory-judge",
        actor_kind=ACTOR_KIND_AGENT,
        actor_metadata={"role": ROLE_FRONTIER_JUDGE},
        custom_fields={
            CUSTOM_FIELD_SPEC_SECTION: "FR-01",
            CUSTOM_FIELD_AC_IDS: ["AC-01"],
            "review_ref": str(review_wi.work_item_id),
        },
    )
    return jury_wi


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestEnsureUpstreamRevisionIntegration:
    """Drive ensure_upstream_revision against InMemoryRegista so schema
    mismatches surface as test failures, not golden-run failures."""

    def test_review_to_implementation_revision_passes_regista_validation(self, runtime, p5_sub):
        """review → implementation revision must pass schema validation end-to-end."""
        iface = _create_interface_spec(p5_sub)
        ts = _create_test_suite(p5_sub, iface)
        review_wi = _create_review_wi(p5_sub, iface, ts)

        route = Route(
            target_state=STATE_NEW,
            create_upstream_revision=True,
            upstream_type=WORK_ITEM_TYPE_IMPLEMENTATION,
            upstream_context_key="review_feedback",
            diagnostics=["Edge case: empty input not handled"],
        )

        # Should not raise — if regista rejects the payload, it will raise here
        ensure_upstream_revision(runtime, review_wi, route)

        # Verify the new implementation exists in regista
        results = p5_sub.query_work_items(
            workflow_name="software_factory",
            work_item_types=[WORK_ITEM_TYPE_IMPLEMENTATION],
        )
        revision_wis = [
            wi
            for wi in results.items
            if (wi.custom_fields or {}).get(CUSTOM_FIELD_UPSTREAM_REVISION_OF)
            == str(review_wi.work_item_id)
        ]
        assert len(revision_wis) == 1, (
            f"Expected exactly one implementation revision, got {len(revision_wis)}"
        )

        cf = revision_wis[0].custom_fields
        assert cf[CUSTOM_FIELD_UPSTREAM_REVISION_OF] == str(review_wi.work_item_id)
        assert CUSTOM_FIELD_INTERFACE_REF in cf
        assert CUSTOM_FIELD_TEST_SUITE_REF in cf
        assert CUSTOM_FIELD_REVIEW_FINDINGS in cf

    def test_jury_to_implementation_revision_passes_regista_validation(self, runtime, p5_sub):
        """jury → implementation revision must pass schema validation end-to-end.

        Regression test for BC-179: jury custom_fields lack interface_ref/test_suite_ref
        because phase4 stage topology does not propagate them from review to jury.
        ensure_upstream_revision resolves both via the jury's review_ref link.
        """
        iface = _create_interface_spec(p5_sub)
        ts = _create_test_suite(p5_sub, iface)
        review_wi = _create_review_wi(p5_sub, iface, ts)
        jury_wi = _create_jury_wi(p5_sub, review_wi)

        route = Route(
            target_state=STATE_NEW,
            create_upstream_revision=True,
            upstream_type=WORK_ITEM_TYPE_IMPLEMENTATION,
            upstream_context_key="jury_feedback",
            diagnostics=["Jury found logic error in AC-01"],
        )

        ensure_upstream_revision(runtime, jury_wi, route)

        results = p5_sub.query_work_items(
            workflow_name="software_factory",
            work_item_types=[WORK_ITEM_TYPE_IMPLEMENTATION],
        )
        revision_wis = [
            wi
            for wi in results.items
            if (wi.custom_fields or {}).get(CUSTOM_FIELD_UPSTREAM_REVISION_OF)
            == str(jury_wi.work_item_id)
        ]
        assert len(revision_wis) == 1, (
            f"Expected exactly one implementation revision from jury, got {len(revision_wis)}"
        )

        cf = revision_wis[0].custom_fields
        assert cf[CUSTOM_FIELD_UPSTREAM_REVISION_OF] == str(jury_wi.work_item_id)
        assert CUSTOM_FIELD_REVIEW_FINDINGS in cf

    def test_idempotency_no_duplicate_revision(self, runtime, p5_sub):
        """Calling ensure_upstream_revision twice on the same source is a no-op."""
        iface = _create_interface_spec(p5_sub)
        ts = _create_test_suite(p5_sub, iface)
        review_wi = _create_review_wi(p5_sub, iface, ts)

        route = Route(
            target_state=STATE_NEW,
            create_upstream_revision=True,
            upstream_type=WORK_ITEM_TYPE_IMPLEMENTATION,
            upstream_context_key="review_feedback",
            diagnostics=["First call"],
        )

        ensure_upstream_revision(runtime, review_wi, route)

        # Fetch the created revision so we can pass it as source on the second call
        # (the idempotency guard checks custom_fields[upstream_revision_of] on the *source*)
        results = p5_sub.query_work_items(
            workflow_name="software_factory",
            work_item_types=[WORK_ITEM_TYPE_IMPLEMENTATION],
        )
        revision_wis_before = [
            wi
            for wi in results.items
            if (wi.custom_fields or {}).get(CUSTOM_FIELD_UPSTREAM_REVISION_OF)
            == str(review_wi.work_item_id)
        ]
        assert len(revision_wis_before) == 1

        # Second call: the guard checks if source_wi.custom_fields has upstream_revision_of.
        # The source here is the *review*, which does NOT have upstream_revision_of.
        # The idempotency guard in ensure_upstream_revision checks the *source* wi, not regista.
        # So a second identical call would create a second item unless the source carries the flag.
        # This matches the mocked test: the guard is on the source work item's custom_fields.
        # To test the real no-duplicate path, simulate a source that already has the marker.
        marked_review = _AlreadyMarkedWI(review_wi, revision_wis_before[0].work_item_id)

        route2 = Route(
            target_state=STATE_NEW,
            create_upstream_revision=True,
            upstream_type=WORK_ITEM_TYPE_IMPLEMENTATION,
            upstream_context_key="review_feedback",
            diagnostics=["Second call — should be no-op"],
        )
        ensure_upstream_revision(runtime, marked_review, route2)

        # Regista should still have exactly one revision
        results_after = p5_sub.query_work_items(
            workflow_name="software_factory",
            work_item_types=[WORK_ITEM_TYPE_IMPLEMENTATION],
        )
        revision_wis_after = [
            wi
            for wi in results_after.items
            if (wi.custom_fields or {}).get(CUSTOM_FIELD_UPSTREAM_REVISION_OF)
            == str(review_wi.work_item_id)
        ]
        assert len(revision_wis_after) == 1, (
            "Second call must not create a duplicate implementation revision"
        )

    def test_schema_drift_canary(self, p5_sub):
        """Directly call regista.create_work_item with the exact custom_fields
        dict that ensure_upstream_revision constructs.  If anyone adds a required
        field to the 'implementation' work_item_type without updating the scheduler,
        this test will fail loudly rather than waiting for a golden run.

        Note: upstream_revision_of is type work_item_ref so it must reference a real
        work item — we use the review_wi created for this canary.
        """
        iface = _create_interface_spec(p5_sub)
        ts = _create_test_suite(p5_sub, iface)
        review_wi = _create_review_wi(p5_sub, iface, ts)

        # Replicate the payload construction from ensure_upstream_revision verbatim
        custom = {
            CUSTOM_FIELD_SPEC_SECTION: "FR-01",
            CUSTOM_FIELD_AC_IDS: ["AC-01"],
            CUSTOM_FIELD_UPSTREAM_REVISION_OF: str(review_wi.work_item_id),
            CUSTOM_FIELD_INTERFACE_REF: str(iface.work_item_id),
            CUSTOM_FIELD_TEST_SUITE_REF: str(ts.work_item_id),
            CUSTOM_FIELD_REVIEW_FINDINGS: {
                "source_wi": str(review_wi.work_item_id),
                "source_type": WORK_ITEM_TYPE_REVIEW,
                "findings": ["Schema drift canary finding"],
            },
        }

        # This must not raise — if it does, ensure_upstream_revision has a live bug
        wi, _ = p5_sub.create_work_item(
            workflow_name="software_factory",
            work_item_type=WORK_ITEM_TYPE_IMPLEMENTATION,
            actor_id=ACTOR_ID_SCHEDULER,
            actor_kind=ACTOR_KIND_AGENT,
            actor_metadata={"role": ROLE_IMPLEMENTER},
            custom_fields=custom,
        )
        assert wi is not None
        assert wi.custom_fields[CUSTOM_FIELD_UPSTREAM_REVISION_OF] == str(review_wi.work_item_id)


class _AlreadyMarkedWI:
    """Thin wrapper that makes a real work item appear to already have
    upstream_revision_of set — used to exercise the idempotency guard."""

    def __init__(self, original, revision_id):
        self._orig = original
        self._revision_id = revision_id

    @property
    def work_item_id(self):
        return self._orig.work_item_id

    @property
    def work_item_type(self):
        return self._orig.work_item_type

    @property
    def custom_fields(self):
        cf = dict(self._orig.custom_fields or {})
        cf[CUSTOM_FIELD_UPSTREAM_REVISION_OF] = str(self._revision_id)
        return cf
