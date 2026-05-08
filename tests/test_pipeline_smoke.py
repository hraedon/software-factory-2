from __future__ import annotations

from pathlib import Path

from factory.channel import InvocationResult
from factory.gate_process import process_gate_item
from factory.runner import process_work_item
from factory.runtime import PipelineRuntime
from factory.scheduler import _ensure_downstream_item

_STAGE_HANDOFF_TEST = {
    "next_type": "test_suite",
    "link_type": "derived_from",
    "next_role": "test_author",
}


class _MultiStageChannel:
    def __init__(self):
        self._name = "fake-multi"
        self._family = "test"
        self._invocations: list = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def family(self) -> str:
        return self._family

    def invoke(self, role, prompt, inputs_dir, outputs_dir, timeout):
        self._invocations.append(role)
        outputs_dir.mkdir(parents=True, exist_ok=True)
        if role == "interface_architect":
            content = (
                "from dataclasses import dataclass\n"
                "def compute(x: int) -> str:\n"
                '    """Satisfies AC-01."""\n'
                "    ...\n"
            )
            name = "artifact.pyi"
            (outputs_dir / name).write_text(content)
            return InvocationResult(success=True, artifact_name=name)
        elif role == "test_author":
            content = (
                "def compute(x: int) -> str:\n"
                "    return str(x)\n\n"
                "def test_compute():\n"
                '    """AC-01"""\n'
                '    assert compute(1) == "1"\n'
            )
            name = "test_suite.py"
            (outputs_dir / name).write_text(content)
            return InvocationResult(success=True, artifact_name=name)
        elif role == "implementer":
            content = "def compute(x: int) -> str:\n    return str(x)\n"
            name = "impl.py"
            (outputs_dir / name).write_text(content)
            return InvocationResult(success=True, artifact_name=name)


class TestPipelineSmoke:
    def test_three_stage_pipeline_with_mock(self, mock_substrate, workspace_root):
        from factory.config import FactoryConfig

        mock_substrate.register_workflow_file(
            str(Path(__file__).parent.parent / "workflows" / "phase2.yaml")
        )
        config = FactoryConfig(
            workspace_root=workspace_root,
            workflow_version=2,
            worker_roles=FactoryConfig.PHASE2_WORKER_ROLES,
            type_to_role=FactoryConfig.PHASE2_TYPE_TO_ROLE,
            roles=FactoryConfig.PHASE2_ROLES,
        )
        channel = _MultiStageChannel()

        mock_substrate.register_actor_role("factory-arch", "interface_architect")
        mock_substrate.register_actor_role("factory-tester", "test_author")
        mock_substrate.register_actor_role("factory-impl", "implementer")
        mock_substrate.register_actor_role("factory-gate", "mechanical_gate")

        iface, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={
                "spec_section": "Compute function: given int x, return str(x).",
                "ac_ids": ["AC-01"],
            },
        )
        assert iface.workflow_version == 2

        # Stage 1: interface_architect
        claim = mock_substrate.acquire_claim(iface.work_item_id, "factory-arch")
        mock_substrate.transition(
            iface.work_item_id,
            "claim",
            "factory-arch",
            actor_metadata={"role": "interface_architect"},
        )
        runtime = PipelineRuntime(
            sub=mock_substrate, config=config, spec_content="Compute function", channel=channel
        )
        process_work_item(
            runtime,
            iface,
            "factory-arch",
            claim,
            "interface_architect",
        )
        iface = mock_substrate.get_work_item(iface.work_item_id)
        assert iface.current_state == "gating"

        # Gate interface_spec
        iface = mock_substrate.get_work_item(iface.work_item_id)
        gate_claim = mock_substrate.acquire_claim(iface.work_item_id, "factory-gate")
        gate_runtime = PipelineRuntime(sub=mock_substrate, config=config)
        process_gate_item(gate_runtime, iface, "factory-gate", gate_claim)
        iface = mock_substrate.get_work_item(iface.work_item_id)
        assert iface.current_state == "locked"

        # Scheduler creates test_suite
        sched_runtime = PipelineRuntime(sub=mock_substrate, config=config)
        _ensure_downstream_item(sched_runtime, iface, _STAGE_HANDOFF_TEST)

        # Find the downstream test_suite
        ts_page = mock_substrate.query_work_items(current_states=["new"], page_size=10)
        ts_wis = [w for w in ts_page.items if w.work_item_type == "test_suite"]
        assert len(ts_wis) == 1
        ts_wi = ts_wis[0]

        # Stage 2: test_author
        claim_ts = mock_substrate.acquire_claim(ts_wi.work_item_id, "factory-tester")
        mock_substrate.transition(
            ts_wi.work_item_id,
            "claim",
            "factory-tester",
            actor_metadata={"role": "test_author"},
        )
        process_work_item(
            PipelineRuntime(
                sub=mock_substrate,
                config=config,
                spec_content="Compute function",
                channel=channel,
            ),
            ts_wi,
            "factory-tester",
            claim_ts,
            "test_author",
        )
        ts_wi = mock_substrate.get_work_item(ts_wi.work_item_id)
        assert ts_wi.current_state == "gating"

        # Gate test_suite
        ts_wi = mock_substrate.get_work_item(ts_wi.work_item_id)
        gate2_claim = mock_substrate.acquire_claim(ts_wi.work_item_id, "factory-gate")
        process_gate_item(gate_runtime, ts_wi, "factory-gate", gate2_claim)
        ts_wi = mock_substrate.get_work_item(ts_wi.work_item_id)
        assert ts_wi.current_state == "locked"

        # Scheduler creates implementation (using test_suite -> implementation handoff)
        ts_handoff = {
            "next_type": "implementation",
            "link_type": "tested_by",
            "additional_links": ["implements"],
            "next_role": "implementer",
        }
        _ensure_downstream_item(sched_runtime, ts_wi, ts_handoff)

        impl_page = mock_substrate.query_work_items(current_states=["new"], page_size=10)
        impl_wis = [w for w in impl_page.items if w.work_item_type == "implementation"]
        assert len(impl_wis) == 1
        impl_wi = impl_wis[0]

        # Stage 3: implementer
        claim_impl = mock_substrate.acquire_claim(impl_wi.work_item_id, "factory-impl")
        mock_substrate.transition(
            impl_wi.work_item_id,
            "claim",
            "factory-impl",
            actor_metadata={"role": "implementer"},
        )
        process_work_item(
            PipelineRuntime(
                sub=mock_substrate,
                config=config,
                spec_content="Compute function",
                channel=channel,
            ),
            impl_wi,
            "factory-impl",
            claim_impl,
            "implementer",
        )
        impl_wi = mock_substrate.get_work_item(impl_wi.work_item_id)
        assert impl_wi.current_state == "gating"

        # Gate implementation
        impl_wi = mock_substrate.get_work_item(impl_wi.work_item_id)
        gate3_claim = mock_substrate.acquire_claim(impl_wi.work_item_id, "factory-gate")
        process_gate_item(gate_runtime, impl_wi, "factory-gate", gate3_claim)
        impl_wi = mock_substrate.get_work_item(impl_wi.work_item_id)
        assert impl_wi.current_state == "locked"

        assert len(channel._invocations) == 3

    def test_gate_fail_routing_returns_to_correct_role(self, mock_substrate, workspace_root):
        from factory.config import FactoryConfig

        mock_substrate.register_workflow_file(
            str(Path(__file__).parent.parent / "workflows" / "phase2.yaml")
        )
        config = FactoryConfig(
            workspace_root=workspace_root,
            workflow_version=2,
            worker_roles=FactoryConfig.PHASE2_WORKER_ROLES,
            type_to_role=FactoryConfig.PHASE2_TYPE_TO_ROLE,
            roles=FactoryConfig.PHASE2_ROLES,
        )

        mock_substrate.register_actor_role("factory-arch", "interface_architect")
        mock_substrate.register_actor_role("factory-gate", "mechanical_gate")

        iface, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={
                "spec_section": "Section",
                "ac_ids": ["AC-01"],
            },
        )

        # Manually submit an empty artifact to gating
        iface_dir = Path(workspace_root) / str(iface.work_item_id) / "attempt-1"
        iface_dir.mkdir(parents=True, exist_ok=True)
        empty_file = iface_dir / "empty.pyi"
        empty_file.write_text("")

        from factory.workspace import compute_sha256

        sha = compute_sha256(b"")
        mock_substrate.transition(
            iface.work_item_id,
            "claim",
            "factory-arch",
            actor_metadata={"role": "interface_architect"},
        )
        mock_substrate.transition(
            iface.work_item_id,
            "submit",
            "factory-arch",
            actor_metadata={"role": "interface_architect"},
            custom_fields={
                "artifact_path": str(empty_file),
                "artifact_hash": sha,
                "ac_ids": ["AC-01"],
            },
        )

        # Gate should fail (empty file)
        iface = mock_substrate.get_work_item(iface.work_item_id)
        gate_claim = mock_substrate.acquire_claim(iface.work_item_id, "factory-gate")
        gate_runtime = PipelineRuntime(sub=mock_substrate, config=config)
        process_gate_item(gate_runtime, iface, "factory-gate", gate_claim)

        updated = mock_substrate.get_work_item(iface.work_item_id)
        assert updated.current_state == "new"

        # Diagnostics should route back to interface_architect
        diagnostics = updated.custom_fields.get("diagnostics", {})
        assert diagnostics.get("diagnostic_kind") == "not_empty"
