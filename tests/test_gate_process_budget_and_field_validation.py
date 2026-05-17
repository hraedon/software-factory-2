from __future__ import annotations

from pathlib import Path

import pytest
from substrate.testing import InMemorySubstrate

from factory.config import FactoryConfig
from factory.constants import (
    CUSTOM_FIELD_DIAGNOSTICS,
    CUSTOM_FIELD_REVIEW_FINDINGS,
)
from factory.gate_process import _wi_type_has_field, process_gate_item
from factory.runtime import PipelineRuntime

PHASE5_WORKFLOW = Path(__file__).parent.parent / "workflows" / "phase5.yaml"

REVIEW_FINDINGS_JSON = (
    '{"passed": false, "findings": '
    '[{"ac_id": "AC-01", "kind": "impl", "severity": "block", "body": "test"}]}'
)


@pytest.fixture()
def phase5_sub():
    sub = InMemorySubstrate()
    sub.register_workflow_file(str(PHASE5_WORKFLOW))
    yield sub
    sub.close()


@pytest.fixture()
def phase5_config(tmp_path):
    return FactoryConfig(
        dsn="",
        project_name="test",
        hmac_key_path="",
        workspace_root=tmp_path / "work",
        workflow_version=5,
    )


class TestWiTypeHasField:
    def test_review_does_not_have_review_findings(self, phase5_sub, phase5_config):
        assert not _wi_type_has_field(phase5_sub, phase5_config, "review", "review_findings")

    def test_implementation_has_review_findings(self, phase5_sub, phase5_config):
        assert _wi_type_has_field(phase5_sub, phase5_config, "implementation", "review_findings")

    def test_implementation_has_diagnostics(self, phase5_sub, phase5_config):
        assert _wi_type_has_field(phase5_sub, phase5_config, "implementation", "diagnostics")

    def test_review_has_diagnostics(self, phase5_sub, phase5_config):
        assert _wi_type_has_field(phase5_sub, phase5_config, "review", "diagnostics")

    def test_unknown_type_returns_false(self, phase5_sub, phase5_config):
        assert not _wi_type_has_field(phase5_sub, phase5_config, "nonexistent_type", "diagnostics")

    def test_unknown_field_returns_false(self, phase5_sub, phase5_config):
        assert not _wi_type_has_field(phase5_sub, phase5_config, "review", "nonexistent_field")

    def test_interface_spec_has_artifact_path(self, phase5_sub, phase5_config):
        assert _wi_type_has_field(phase5_sub, phase5_config, "interface_spec", "artifact_path")

    def test_jury_has_review_ref(self, phase5_sub, phase5_config):
        assert _wi_type_has_field(phase5_sub, phase5_config, "jury", "review_ref")


class TestReviewFindingsFilteredOnReviewType:
    def test_review_findings_not_written_to_review_wi(self, phase5_sub, phase5_config, tmp_path):
        iface_wi, _ = phase5_sub.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={"spec_section": "Test", "ac_ids": ["AC-01"]},
        )
        test_wi, _ = phase5_sub.create_work_item(
            workflow_name="software_factory",
            work_item_type="test_suite",
            actor_id="test-creator",
            custom_fields={
                "spec_section": "Test",
                "ac_ids": ["AC-01"],
                "interface_ref": str(iface_wi.work_item_id),
            },
        )
        impl_wi, _ = phase5_sub.create_work_item(
            workflow_name="software_factory",
            work_item_type="implementation",
            actor_id="test-creator",
            custom_fields={
                "spec_section": "Test",
                "ac_ids": ["AC-01"],
                "interface_ref": str(iface_wi.work_item_id),
                "test_suite_ref": str(test_wi.work_item_id),
            },
        )
        review_wi, _ = phase5_sub.create_work_item(
            workflow_name="software_factory",
            work_item_type="review",
            actor_id="test-creator",
            custom_fields={
                "spec_section": "Test",
                "ac_ids": ["AC-01"],
                "interface_ref": str(iface_wi.work_item_id),
                "test_suite_ref": str(test_wi.work_item_id),
                "implementation_ref": str(impl_wi.work_item_id),
            },
        )
        artifact_path = tmp_path / "review.json"
        artifact_path.write_text(REVIEW_FINDINGS_JSON)
        phase5_sub.transition(
            review_wi.work_item_id,
            "claim",
            "test-reviewer",
            actor_metadata={"role": "cross_family_reviewer"},
        )
        phase5_sub.transition(
            review_wi.work_item_id,
            "submit",
            "test-reviewer",
            actor_metadata={"role": "cross_family_reviewer"},
            custom_fields={
                "artifact_path": str(artifact_path),
                "artifact_hash": "abc",
            },
        )
        phase5_sub.register_actor_role("test-gate-rv", "mechanical_gate")
        claim = phase5_sub.acquire_claim(review_wi.work_item_id, "test-gate-rv", ttl_seconds=300)
        fresh = phase5_sub.get_work_item(review_wi.work_item_id)

        runtime = PipelineRuntime(sub=phase5_sub, config=phase5_config)
        process_gate_item(runtime, fresh, "test-gate-rv", claim)

        final = phase5_sub.get_work_item(review_wi.work_item_id)
        assert final.current_state == "new"
        custom_fields = final.custom_fields or {}
        assert CUSTOM_FIELD_REVIEW_FINDINGS not in custom_fields, (
            f"review_findings should NOT be on review type, but found: {custom_fields}"
        )
        assert CUSTOM_FIELD_DIAGNOSTICS in custom_fields, (
            f"diagnostics should be on review type, but missing: {custom_fields}"
        )


class TestGateBudgetGuardrail:
    def test_attempt_threshold_blocks_over_budget_items(self, phase5_sub, phase5_config):
        iface_wi, _ = phase5_sub.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={"spec_section": "Test", "ac_ids": ["AC-01"]},
        )
        phase5_sub.register_actor_role("test-gate-budget", "mechanical_gate")
        phase5_sub.transition(
            iface_wi.work_item_id,
            "claim",
            "test-worker",
            actor_metadata={"role": "interface_architect"},
        )
        phase5_sub.transition(
            iface_wi.work_item_id,
            "submit",
            "test-worker",
            actor_metadata={"role": "interface_architect"},
            custom_fields={"artifact_path": "/nonexistent.pyi", "artifact_hash": "abc"},
        )
        for _ in range(phase5_config.attempt_threshold):
            phase5_sub.acquire_claim(iface_wi.work_item_id, "test-gate-budget", ttl_seconds=300)
            phase5_sub.release_claim(iface_wi.work_item_id, "test-gate-budget")

        claim = phase5_sub.acquire_claim(iface_wi.work_item_id, "test-gate-budget", ttl_seconds=300)
        assert claim.attempt_number >= phase5_config.attempt_threshold

        wi = phase5_sub.get_work_item(iface_wi.work_item_id)
        assert wi.current_state == "gating"

    def test_near_budget_items_remain_in_gating_state(self, phase5_sub, phase5_config):
        iface_wi, _ = phase5_sub.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={"spec_section": "Test", "ac_ids": ["AC-01"]},
        )
        phase5_sub.register_actor_role("test-gate-budget2", "mechanical_gate")
        phase5_sub.transition(
            iface_wi.work_item_id,
            "claim",
            "test-worker",
            actor_metadata={"role": "interface_architect"},
        )
        phase5_sub.transition(
            iface_wi.work_item_id,
            "submit",
            "test-worker",
            actor_metadata={"role": "interface_architect"},
            custom_fields={"artifact_path": "/nonexistent.pyi", "artifact_hash": "abc"},
        )
        claim = phase5_sub.acquire_claim(
            iface_wi.work_item_id, "test-gate-budget2", ttl_seconds=300
        )
        assert claim.attempt_number == 1
        assert claim.attempt_number < phase5_config.attempt_threshold
