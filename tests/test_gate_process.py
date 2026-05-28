from __future__ import annotations

import pytest

from factory.gate_process import process_gate_item
from factory.runtime import PipelineRuntime


@pytest.mark.integration
class TestGateProcessIntegration:
    def test_gate_passes_valid_artifact(self, regista, workspace_root, tmp_path, factory_config):
        wi, _ = regista.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={
                "spec_section": "Test",
                "ac_ids": ["AC-01"],
            },
        )
        artifact_path = tmp_path / "test_interface.pyi"
        artifact_path.write_text('"""Satisfies AC-01."""\ndef foo(x: int) -> str: ...\n')
        regista.transition(
            wi.work_item_id,
            "claim",
            "test-worker",
            actor_metadata={"role": "interface_architect"},
        )
        regista.transition(
            wi.work_item_id,
            "submit",
            "test-worker",
            actor_metadata={"role": "interface_architect"},
            custom_fields={
                "artifact_path": str(artifact_path),
                "artifact_hash": "abc",
            },
        )
        regista.register_actor_role("test-gate", "mechanical_gate")
        gate_claim = regista.acquire_claim(wi.work_item_id, "test-gate", ttl_seconds=300)
        fresh = regista.get_work_item(wi.work_item_id)

        gate_runtime = PipelineRuntime(sub=regista, config=factory_config)
        process_gate_item(gate_runtime, fresh, "test-gate", gate_claim)

        final = regista.get_work_item(wi.work_item_id)
        assert final.current_state == "locked"

    def test_gate_fails_invalid_artifact(self, regista, workspace_root, tmp_path, factory_config):
        wi, _ = regista.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={
                "spec_section": "Test",
                "ac_ids": ["AC-01", "AC-02"],
            },
        )
        artifact_path = tmp_path / "bad_interface.pyi"
        artifact_path.write_text('"""Satisfies AC-01."""\ndef foo(x: int) -> str: ...\n')
        regista.transition(
            wi.work_item_id,
            "claim",
            "test-worker",
            actor_metadata={"role": "interface_architect"},
        )
        regista.transition(
            wi.work_item_id,
            "submit",
            "test-worker",
            actor_metadata={"role": "interface_architect"},
            custom_fields={
                "artifact_path": str(artifact_path),
                "artifact_hash": "abc",
            },
        )
        regista.register_actor_role("test-gate-fail", "mechanical_gate")
        gate_claim = regista.acquire_claim(wi.work_item_id, "test-gate-fail", ttl_seconds=300)
        fresh = regista.get_work_item(wi.work_item_id)

        gate_runtime = PipelineRuntime(sub=regista, config=factory_config)
        process_gate_item(gate_runtime, fresh, "test-gate-fail", gate_claim)

        final = regista.get_work_item(wi.work_item_id)
        assert final.current_state == "new"

    def test_gate_fails_missing_artifact(self, regista, workspace_root, tmp_path, factory_config):
        wi, _ = regista.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={
                "spec_section": "Test",
                "ac_ids": ["AC-01"],
                "artifact_path": str(tmp_path / "nonexistent.pyi"),
            },
        )
        regista.transition(
            wi.work_item_id,
            "claim",
            "test-worker",
            actor_metadata={"role": "interface_architect"},
        )
        regista.transition(
            wi.work_item_id,
            "submit",
            "test-worker",
            actor_metadata={"role": "interface_architect"},
            custom_fields={
                "artifact_path": str(tmp_path / "nonexistent.pyi"),
                "artifact_hash": "abc",
            },
        )
        regista.register_actor_role("test-gate-missing", "mechanical_gate")
        gate_claim = regista.acquire_claim(wi.work_item_id, "test-gate-missing", ttl_seconds=300)
        fresh = regista.get_work_item(wi.work_item_id)

        gate_runtime = PipelineRuntime(sub=regista, config=factory_config)
        process_gate_item(gate_runtime, fresh, "test-gate-missing", gate_claim)

        final = regista.get_work_item(wi.work_item_id)
        assert final.current_state == "new"
