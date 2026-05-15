from __future__ import annotations

import json
from pathlib import Path

import pytest
from substrate.testing import InMemorySubstrate

from factory.config import FactoryConfig
from factory.gate_process import process_gate_item
from factory.runtime import PipelineRuntime

PHASE5_WORKFLOW = Path(__file__).parent.parent / "workflows" / "phase5.yaml"


def _claim_and_submit(sub, wi, role, artifact_path):
    sub.transition(wi.work_item_id, "claim", "worker", actor_metadata={"role": role})
    sub.transition(
        wi.work_item_id,
        "submit",
        "worker",
        actor_metadata={"role": role},
        custom_fields={"artifact_path": str(artifact_path), "artifact_hash": "abc"},
    )


def _fresh_gate_claim(sub, wi):
    sub.register_actor_role("gate", "mechanical_gate")
    claim = sub.acquire_claim(wi.work_item_id, "gate", ttl_seconds=300)
    return sub.get_work_item(wi.work_item_id), claim


@pytest.fixture()
def mock_config(tmp_path):
    return FactoryConfig(
        dsn="",
        project_name="test",
        hmac_key_path="",
        workspace_root=tmp_path / "work",
    )


@pytest.fixture()
def phase5_sub():
    sub = InMemorySubstrate()
    sub.register_workflow(PHASE5_WORKFLOW.read_text())
    yield sub
    sub.close()


class TestGateProcessPhase5Mock:
    def test_gate_passes_integration_artifact(self, phase5_sub, mock_config, tmp_path):
        artifact = tmp_path / "integration.json"
        artifact.write_text(
            json.dumps(
                {
                    "assembled_tree": {
                        "mathlib.py": ("def square(x: int) -> int:\n    return x * x\n"),
                    },
                    "entry_point": "mathlib.square",
                    "integration_tests": (
                        "\n"
                        "import mathlib\n\n"
                        "def test_square():\n"
                        "    assert mathlib.square(4) == 16\n"
                    ),
                }
            )
        )
        wi, _ = phase5_sub.create_work_item(
            workflow_name="software_factory",
            work_item_type="integration",
            actor_id="integrator",
            custom_fields={
                "spec_section": "Test",
                "ac_ids": ["AC-01"],
            },
        )
        _claim_and_submit(phase5_sub, wi, "integrator", artifact)
        fresh, claim = _fresh_gate_claim(phase5_sub, wi)
        runtime = PipelineRuntime(sub=phase5_sub, config=mock_config)
        process_gate_item(runtime, fresh, "gate", claim)
        assert phase5_sub.get_work_item(wi.work_item_id).current_state == "locked"

    def test_gate_fails_integration_mypy(self, phase5_sub, mock_config, tmp_path):
        artifact = tmp_path / "integration.json"
        artifact.write_text(
            json.dumps(
                {
                    "assembled_tree": {
                        "typed.py": "def greet(name: str) -> str:\n    return name\n",
                        "caller.py": (
                            "import typed\n\ndef bad() -> str:\n    return typed.greet(123)\n"
                        ),
                    },
                    "entry_point": "caller.bad",
                    "integration_tests": "def test_nothing(): pass\n",
                }
            )
        )
        wi, _ = phase5_sub.create_work_item(
            workflow_name="software_factory",
            work_item_type="integration",
            actor_id="integrator",
            custom_fields={
                "spec_section": "Test",
                "ac_ids": ["AC-01"],
            },
        )
        _claim_and_submit(phase5_sub, wi, "integrator", artifact)
        fresh, claim = _fresh_gate_claim(phase5_sub, wi)
        runtime = PipelineRuntime(sub=phase5_sub, config=mock_config)
        process_gate_item(runtime, fresh, "gate", claim)
        final = phase5_sub.get_work_item(wi.work_item_id)
        assert final.current_state == "new"
        assert "diagnostics" in (final.custom_fields or {})

    def test_gate_passes_outcome_verification(self, phase5_sub, mock_config, tmp_path):
        int_artifact = tmp_path / "integration.json"
        int_artifact.write_text(json.dumps({"assembled_tree": {}}))
        int_wi, _ = phase5_sub.create_work_item(
            workflow_name="software_factory",
            work_item_type="integration",
            actor_id="int",
            custom_fields={"spec_section": "T", "ac_ids": []},
        )
        _claim_and_submit(phase5_sub, int_wi, "integrator", int_artifact)

        artifact = tmp_path / "outcome.json"
        artifact.write_text(
            json.dumps(
                {
                    "verdict": "pass",
                    "rationale": "All ACs satisfied",
                    "routing_hint": None,
                }
            )
        )
        wi, _ = phase5_sub.create_work_item(
            workflow_name="software_factory",
            work_item_type="outcome_verification",
            actor_id="verifier",
            custom_fields={
                "spec_section": "Test",
                "ac_ids": ["AC-01"],
                "integration_ref": str(int_wi.work_item_id),
            },
        )
        _claim_and_submit(phase5_sub, wi, "outcome_verifier", artifact)
        fresh, claim = _fresh_gate_claim(phase5_sub, wi)
        runtime = PipelineRuntime(sub=phase5_sub, config=mock_config)
        process_gate_item(runtime, fresh, "gate", claim)
        assert phase5_sub.get_work_item(wi.work_item_id).current_state == "locked"

    def test_gate_fails_outcome_verification(self, phase5_sub, mock_config, tmp_path):
        int_artifact = tmp_path / "integration.json"
        int_artifact.write_text(json.dumps({"assembled_tree": {}}))
        int_wi, _ = phase5_sub.create_work_item(
            workflow_name="software_factory",
            work_item_type="integration",
            actor_id="int",
            custom_fields={"spec_section": "T", "ac_ids": []},
        )
        _claim_and_submit(phase5_sub, int_wi, "integrator", int_artifact)

        artifact = tmp_path / "outcome.json"
        artifact.write_text(
            json.dumps(
                {
                    "verdict": "fail",
                    "rationale": "Missing AC coverage",
                    "routing_hint": {"work_item_type": "implementation", "reason": "stub"},
                }
            )
        )
        wi, _ = phase5_sub.create_work_item(
            workflow_name="software_factory",
            work_item_type="outcome_verification",
            actor_id="verifier",
            custom_fields={
                "spec_section": "Test",
                "ac_ids": ["AC-01"],
                "integration_ref": str(int_wi.work_item_id),
            },
        )
        _claim_and_submit(phase5_sub, wi, "outcome_verifier", artifact)
        fresh, claim = _fresh_gate_claim(phase5_sub, wi)
        runtime = PipelineRuntime(sub=phase5_sub, config=mock_config)
        process_gate_item(runtime, fresh, "gate", claim)
        final = phase5_sub.get_work_item(wi.work_item_id)
        assert final.current_state == "cannot_proceed"
        assert "diagnostics" in (final.custom_fields or {})
        diags = (final.custom_fields or {}).get("diagnostics", {})
        assert diags.get("routing_hint") == {
            "work_item_type": "implementation",
            "reason": "stub",
        }


class TestGateProcessPhase5Integration:
    @pytest.mark.integration
    def test_gate_passes_integration_artifact(
        self, phase5_substrate, tmp_path, phase5_factory_config
    ):
        artifact = tmp_path / "integration.json"
        artifact.write_text(
            json.dumps(
                {
                    "assembled_tree": {
                        "mathlib.py": ("def square(x: int) -> int:\n    return x * x\n"),
                    },
                    "entry_point": "mathlib.square",
                    "integration_tests": (
                        "\n"
                        "import mathlib\n\n"
                        "def test_square():\n"
                        "    assert mathlib.square(4) == 16\n"
                    ),
                }
            )
        )
        wi, _ = phase5_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="integration",
            actor_id="integrator",
            custom_fields={
                "spec_section": "Test",
                "ac_ids": ["AC-01"],
            },
        )
        _claim_and_submit(phase5_substrate, wi, "integrator", artifact)
        fresh, claim = _fresh_gate_claim(phase5_substrate, wi)
        runtime = PipelineRuntime(sub=phase5_substrate, config=phase5_factory_config)
        process_gate_item(runtime, fresh, "gate", claim)
        assert phase5_substrate.get_work_item(wi.work_item_id).current_state == "locked"

    @pytest.mark.integration
    def test_gate_fails_integration_mypy(self, phase5_substrate, tmp_path, phase5_factory_config):
        artifact = tmp_path / "integration.json"
        artifact.write_text(
            json.dumps(
                {
                    "assembled_tree": {
                        "typed.py": "def greet(name: str) -> str:\n    return name\n",
                        "caller.py": (
                            "import typed\n\ndef bad() -> str:\n    return typed.greet(123)\n"
                        ),
                    },
                    "entry_point": "caller.bad",
                    "integration_tests": "def test_nothing(): pass\n",
                }
            )
        )
        wi, _ = phase5_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="integration",
            actor_id="integrator",
            custom_fields={
                "spec_section": "Test",
                "ac_ids": ["AC-01"],
            },
        )
        _claim_and_submit(phase5_substrate, wi, "integrator", artifact)
        fresh, claim = _fresh_gate_claim(phase5_substrate, wi)
        runtime = PipelineRuntime(sub=phase5_substrate, config=phase5_factory_config)
        process_gate_item(runtime, fresh, "gate", claim)
        final = phase5_substrate.get_work_item(wi.work_item_id)
        assert final.current_state == "new"
        assert "diagnostics" in (final.custom_fields or {})

    @pytest.mark.integration
    def test_gate_fails_outcome_verification_routing_hint(
        self, phase5_substrate, tmp_path, phase5_factory_config
    ):
        int_artifact = tmp_path / "integration.json"
        int_artifact.write_text(json.dumps({"assembled_tree": {}}))
        int_wi, _ = phase5_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="integration",
            actor_id="int",
            custom_fields={"spec_section": "T", "ac_ids": []},
        )
        _claim_and_submit(phase5_substrate, int_wi, "integrator", int_artifact)

        artifact = tmp_path / "outcome.json"
        artifact.write_text(
            json.dumps(
                {
                    "verdict": "fail",
                    "rationale": "Missing AC coverage",
                    "routing_hint": {
                        "work_item_type": "implementation",
                        "reason": "stub coverage gap",
                    },
                }
            )
        )
        wi, _ = phase5_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="outcome_verification",
            actor_id="verifier",
            custom_fields={
                "spec_section": "Test",
                "ac_ids": ["AC-01"],
                "integration_ref": str(int_wi.work_item_id),
            },
        )
        _claim_and_submit(phase5_substrate, wi, "outcome_verifier", artifact)
        fresh, claim = _fresh_gate_claim(phase5_substrate, wi)
        runtime = PipelineRuntime(sub=phase5_substrate, config=phase5_factory_config)
        process_gate_item(runtime, fresh, "gate", claim)
        final = phase5_substrate.get_work_item(wi.work_item_id)
        assert final.current_state == "cannot_proceed"
        diagnostics = (final.custom_fields or {}).get("diagnostics", {})
        assert "routing_hint" in diagnostics
        assert diagnostics["routing_hint"]["work_item_type"] == "implementation"
