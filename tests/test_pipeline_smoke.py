from __future__ import annotations

from pathlib import Path

from factory.channel import InvocationResult
from factory.config import FactoryConfig, StageHandoff
from factory.constants import (
    CUSTOM_FIELD_INTERFACE_REF,
    CUSTOM_FIELD_TEST_SUITE_REF,
    LINK_TYPE_DERIVED_FROM,
    LINK_TYPE_TESTED_BY,
    WORK_ITEM_TYPE_IMPLEMENTATION,
    WORK_ITEM_TYPE_INTERFACE_SPEC,
    WORK_ITEM_TYPE_TEST_SUITE,
)
from factory.gate_process import process_gate_item
from factory.runner import process_work_item
from factory.runtime import PipelineRuntime
from factory.scheduler import _ensure_downstream_item

_STAGE_HANDOFF_TEST = StageHandoff(
    source_type=WORK_ITEM_TYPE_INTERFACE_SPEC,
    source_state="locked",
    target_type=WORK_ITEM_TYPE_TEST_SUITE,
    link_type=LINK_TYPE_DERIVED_FROM,
    ref_field=CUSTOM_FIELD_INTERFACE_REF,
)


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

    def invoke(self, role, prompt, outputs_dir, timeout, extra_env=None):
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
        mock_substrate.register_workflow_file(
            str(Path(__file__).parent.parent / "workflows" / "phase2.yaml")
        )
        config = FactoryConfig.phase2(workspace_root=workspace_root)
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
        ts_handoff = StageHandoff(
            source_type=WORK_ITEM_TYPE_TEST_SUITE,
            source_state="locked",
            target_type=WORK_ITEM_TYPE_IMPLEMENTATION,
            link_type=LINK_TYPE_TESTED_BY,
            additional_links=("implements",),
            ref_field=CUSTOM_FIELD_TEST_SUITE_REF,
            propagate_fields=(CUSTOM_FIELD_INTERFACE_REF,),
        )
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
        mock_substrate.register_workflow_file(
            str(Path(__file__).parent.parent / "workflows" / "phase2.yaml")
        )
        config = FactoryConfig.phase2(workspace_root=workspace_root)

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


class TestWorkflowCompositionAppendFields:
    def test_phase4_impl_has_upstream_revision_of_with_target_types(self):
        from substrate.testing import InMemorySubstrate

        phase4_path = str(Path(__file__).parent.parent / "workflows" / "phase4.yaml")
        sub = InMemorySubstrate()
        sub.register_workflow_file(phase4_path)
        wf = sub._workflows
        try:
            for _key, w in wf.items():
                for wit in w.get("work_item_types", []):
                    if wit["name"] != "implementation":
                        continue
                    cf_names = [cf["name"] for cf in wit.get("custom_fields", [])]
                    assert "upstream_revision_of" in cf_names, (
                        f"upstream_revision_of missing from implementation after "
                        f"phase4 composition. Got: {cf_names}"
                    )
                    assert "review_findings" in cf_names, (
                        f"review_findings missing from implementation after "
                        f"phase4 composition. Got: {cf_names}"
                    )
                    for cf in wit.get("custom_fields", []):
                        if cf["name"] == "upstream_revision_of":
                            targets = cf.get("target_work_item_types")
                            assert targets == ["review", "jury"], (
                                f"upstream_revision_of target_work_item_types "
                                f"should be [review, jury], got {targets}"
                            )
        finally:
            sub.close()

    def test_phase2_impl_lacks_upstream_revision_of(self):
        from substrate.testing import InMemorySubstrate

        phase2_path = str(Path(__file__).parent.parent / "workflows" / "phase2.yaml")
        sub = InMemorySubstrate()
        sub.register_workflow_file(phase2_path)
        wf = sub._workflows
        try:
            for _key, w in wf.items():
                for wit in w.get("work_item_types", []):
                    if wit["name"] != "implementation":
                        continue
                    cf_names = [cf["name"] for cf in wit.get("custom_fields", [])]
                    assert "upstream_revision_of" not in cf_names, (
                        f"upstream_revision_of should NOT be in phase2 implementation. "
                        f"Got: {cf_names}"
                    )
                    assert "review_findings" not in cf_names, (
                        f"review_findings should NOT be in phase2 implementation. Got: {cf_names}"
                    )
        finally:
            sub.close()
