from __future__ import annotations

import pytest


@pytest.mark.integration
class TestGateProcessIntegration:
    def test_gate_process_passes_valid_artifact(self, substrate, workspace_root, tmp_path):
        wi, _ = substrate.create_work_item(
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
        substrate.transition(
            wi.work_item_id,
            "claim",
            "test-worker",
            actor_metadata={"role": "interface_architect"},
        )
        substrate.transition(
            wi.work_item_id,
            "submit",
            "test-worker",
            actor_metadata={"role": "interface_architect"},
            custom_fields={
                "artifact_path": str(artifact_path),
                "artifact_hash": "abc",
                "ac_ids": ["AC-01"],
            },
        )
        assert wi.work_item_type == "interface_spec"
