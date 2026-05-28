from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from regista._testing import drop_project_schema

from factory.channel import InvocationResult
from factory.config import FactoryConfig
from factory.gate_process import process_gate_item
from factory.phase_defaults import PHASE2_ROLES, PHASE2_TYPE_TO_ROLE, PHASE2_WORKER_ROLES
from factory.runner import process_work_item
from factory.runtime import PipelineRuntime

TESTS_DIR = Path(__file__).parent
DSN = "postgresql://regista_test:regista_test@localhost:5432/regista_test"
KEY_PATH = str(TESTS_DIR / "test_keys.json")
PHASE2_PATH = str(Path(__file__).parent.parent / "workflows" / "phase2.yaml")


class _RealSmokeChannel:
    def __init__(self):
        self._name = "real-smoke"
        self._family = "test"

    @property
    def name(self) -> str:
        return self._name

    @property
    def family(self) -> str:
        return self._family

    def invoke(self, role, prompt, outputs_dir, timeout, extra_env=None):
        outputs_dir.mkdir(parents=True, exist_ok=True)
        content = (
            "from dataclasses import dataclass\n"
            "def compute(x: int) -> str:\n"
            '    """AC-01"""\n'
            "    ...\n"
        )
        name = "artifact.pyi"
        (outputs_dir / name).write_text(content)
        return InvocationResult(success=True, artifact_name=name)


@pytest.fixture(scope="function")
def real_regista():
    from regista import Regista

    project = f"sf2_real_{uuid.uuid4().hex[:8]}"
    sub = Regista.create_project(DSN, project, KEY_PATH)
    sub.register_workflow_file(PHASE2_PATH)
    yield sub
    sub.close()
    drop_project_schema(DSN, project)


@pytest.mark.integration
class TestPipelineIntegrationReal:
    """Smoke test exercising the interface_spec pipeline against a real Postgres
    Regista.  One stage is sufficient — InMemoryRegista parity covers the rest."""

    def test_interface_spec_lifecycle_on_real_regista(self, real_regista, workspace_root):
        config = FactoryConfig(
            dsn=DSN,
            project_name=real_regista.project,
            hmac_key_path=KEY_PATH,
            workspace_root=workspace_root,
            workflow_version=2,
            worker_roles=PHASE2_WORKER_ROLES,
            type_to_role=PHASE2_TYPE_TO_ROLE,
            roles=PHASE2_ROLES,
        )
        channel = _RealSmokeChannel()

        real_regista.register_actor_role("factory-arch", "interface_architect")
        real_regista.register_actor_role("factory-gate", "mechanical_gate")

        iface, _ = real_regista.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={
                "spec_section": "Compute function: given int x, return str(x).",
                "ac_ids": ["AC-01"],
            },
        )
        assert iface.workflow_version == 2

        claim = real_regista.acquire_claim(iface.work_item_id, "factory-arch")
        real_regista.transition(
            iface.work_item_id,
            "claim",
            "factory-arch",
            actor_metadata={"role": "interface_architect"},
        )
        runtime = PipelineRuntime(
            sub=real_regista, config=config, spec_content="Compute function", channel=channel
        )
        process_work_item(
            runtime,
            iface,
            "factory-arch",
            claim,
            "interface_architect",
        )
        iface = real_regista.get_work_item(iface.work_item_id)
        assert iface.current_state == "gating"

        gate_claim = real_regista.acquire_claim(iface.work_item_id, "factory-gate")
        gate_runtime = PipelineRuntime(sub=real_regista, config=config)
        process_gate_item(gate_runtime, iface, "factory-gate", gate_claim)
        iface = real_regista.get_work_item(iface.work_item_id)
        assert iface.current_state == "locked"

        events = real_regista.read_events(work_item_id=iface.work_item_id)
        transitions = [e.transition for e in events]
        assert "created" in transitions
        assert "claim" in transitions
        assert "submit" in transitions
        assert "gate_pass" in transitions
