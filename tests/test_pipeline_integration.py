from __future__ import annotations

from pathlib import Path

from factory.channel import InvocationResult
from factory.config import FactoryConfig, StageHandoff
from factory.constants import (
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


class _IntegrationChannel:
    def __init__(self, workspace_root: Path):
        self._workspace_root = workspace_root
        self._name = "integration-test"
        self._family = "test"
        self._invocations: list[tuple[str, int]] = []
        self._role_attempt_counts: dict[str, int] = {}
        self._fail_at: dict[tuple[str, int], str] = {}
        self._pending_ac_ids: list[str] = ["AC-01"]

    @property
    def name(self) -> str:
        return self._name

    @property
    def family(self) -> str:
        return self._family

    def scripted_failure(
        self,
        role: str,
        attempt_number: int,
        error: str = "scripted_failure",
    ) -> None:
        self._fail_at[(role, attempt_number)] = error

    def invoke(self, role, prompt, outputs_dir, timeout, extra_env=None):
        n = self._role_attempt_counts.get(role, 0) + 1
        self._role_attempt_counts[role] = n
        self._invocations.append((role, n))

        if (role, n) in self._fail_at:
            return InvocationResult(
                success=False,
                error_message=self._fail_at[(role, n)],
                exit_code=1,
            )

        outputs_dir.mkdir(parents=True, exist_ok=True)
        ac = self._pending_ac_ids[0] if self._pending_ac_ids else "AC-01"

        if role == "interface_architect":
            content = (
                "from dataclasses import dataclass\n"
                "def compute(x: int) -> str:\n"
                f'    """{ac}"""\n'
                "    ...\n"
            )
            name = "artifact.pyi"
        elif role == "test_author":
            content = (
                "def compute(x: int) -> str:\n"
                "    return str(x)\n\n"
                "def test_compute():\n"
                f'    """{ac}"""\n'
                '    assert compute(1) == "1"\n'
            )
            name = "test_suite.py"
        elif role == "implementer":
            content = "def compute(x: int) -> str:\n    return str(x)\n"
            name = "impl.py"
        else:
            return InvocationResult(
                success=False,
                error_message=f"unknown role {role}",
                exit_code=1,
            )

        (outputs_dir / name).write_text(content)
        return InvocationResult(success=True, artifact_name=name)

    @property
    def invocations(self) -> list[tuple[str, int]]:
        return list(self._invocations)


def _make_phase2_config(workspace_root: Path) -> FactoryConfig:
    return FactoryConfig.phase2(workspace_root=workspace_root)


def _register_roles(sub):
    for actor_id, role in [
        ("factory-arch", "interface_architect"),
        ("factory-tester", "test_author"),
        ("factory-impl", "implementer"),
        ("factory-gate", "mechanical_gate"),
    ]:
        sub.register_actor_role(actor_id, role)


def _run_worker_stage(runtime, channel, wi, actor_id, role_name, spec_content="Test spec"):
    claim = runtime.sub.acquire_claim(wi.work_item_id, actor_id)
    runtime.sub.transition(
        wi.work_item_id,
        "claim",
        actor_id,
        actor_metadata={"role": role_name},
    )
    runtime_with_spec = PipelineRuntime(
        sub=runtime.sub, config=runtime.config, spec_content=spec_content, channel=channel
    )
    process_work_item(
        runtime_with_spec,
        wi,
        actor_id,
        claim,
        role_name,
    )
    return runtime.sub.get_work_item(wi.work_item_id)


def _run_gate(runtime, wi, actor_id="factory-gate"):
    claim = runtime.sub.acquire_claim(wi.work_item_id, actor_id)
    runtime_gate = PipelineRuntime(sub=runtime.sub, config=runtime.config)
    process_gate_item(runtime_gate, wi, actor_id, claim)
    return runtime.sub.get_work_item(wi.work_item_id)


_HANDOFF_MAP = {
    ("interface_spec", "locked"): StageHandoff(
        source_type=WORK_ITEM_TYPE_INTERFACE_SPEC,
        source_state="locked",
        target_type=WORK_ITEM_TYPE_TEST_SUITE,
        link_type=LINK_TYPE_DERIVED_FROM,
    ),
    ("test_suite", "locked"): StageHandoff(
        source_type=WORK_ITEM_TYPE_TEST_SUITE,
        source_state="locked",
        target_type=WORK_ITEM_TYPE_IMPLEMENTATION,
        link_type=LINK_TYPE_TESTED_BY,
        additional_links=("implements",),
    ),
}


def _create_downstream(runtime, source_wi, source_type, source_state):
    handoff = _HANDOFF_MAP.get((source_type, source_state))
    if handoff is None:
        return None
    sched_runtime = PipelineRuntime(sub=runtime.sub, config=runtime.config)
    _ensure_downstream_item(sched_runtime, source_wi, handoff)

    downstream = None
    for wi in runtime.sub.query_work_items(current_states=["new"], page_size=50).items:
        if wi.work_item_type == handoff.target_type:
            ref_field = "interface_ref" if handoff.target_type == "test_suite" else "test_suite_ref"
            cf = wi.custom_fields or {}
            if cf.get(ref_field) == str(source_wi.work_item_id):
                downstream = wi
                break
    return downstream


def _drive_full_pipeline(runtime, channel, spec_section="Compute function", ac_ids=None):
    if ac_ids is None:
        ac_ids = ["AC-01"]

    iface, _ = runtime.sub.create_work_item(
        workflow_name="software_factory",
        work_item_type="interface_spec",
        actor_id="test-creator",
        custom_fields={"spec_section": spec_section, "ac_ids": ac_ids},
    )

    # Stage 1: interface_architect
    wi = _run_worker_stage(
        runtime,
        channel,
        iface,
        "factory-arch",
        "interface_architect",
        spec_section,
    )
    assert wi.current_state == "gating", f"Expected gating, got {wi.current_state}"
    wi = _run_gate(runtime, wi)
    assert wi.current_state == "locked", f"Expected locked after gate, got {wi.current_state}"

    # Schedule + run test_suite
    ts_wi = _create_downstream(runtime, wi, "interface_spec", "locked")
    assert ts_wi is not None, "test_suite work item not created"
    wi = _run_worker_stage(
        runtime,
        channel,
        ts_wi,
        "factory-tester",
        "test_author",
        spec_section,
    )
    assert wi.current_state == "gating"
    wi = _run_gate(runtime, wi)
    assert wi.current_state == "locked"

    # Schedule + run implementation
    impl_wi = _create_downstream(runtime, wi, "test_suite", "locked")
    assert impl_wi is not None, "implementation work item not created"
    wi = _run_worker_stage(
        runtime,
        channel,
        impl_wi,
        "factory-impl",
        "implementer",
        spec_section,
    )
    assert wi.current_state == "gating"
    wi = _run_gate(runtime, wi)
    assert wi.current_state == "locked"

    return {
        "interface_spec": iface,
        "test_suite": ts_wi,
        "implementation": impl_wi,
    }


class _BadImplIntegrationChannel(_IntegrationChannel):
    """Produces implementation artifacts that trigger impl_lint gate failures
    (bare except, which ruff cannot auto-fix) for escalation testing."""

    def invoke(self, role, prompt, outputs_dir, timeout, extra_env=None):
        result = super().invoke(role, prompt, outputs_dir, timeout)
        if role == "implementer" and result.success:
            name = result.artifact_name
            (outputs_dir / name).write_text(
                "def compute(x: int) -> str:\n"
                "    try:\n"
                "        return str(x)\n"
                "    except:\n"
                '        return ""\n'
            )
        return result


class TestPipelineIntegration:
    def test_three_item_subset_end_to_end(self, mock_substrate, workspace_root):
        mock_substrate.register_workflow_file(
            str(Path(__file__).parent.parent / "workflows" / "phase2.yaml")
        )
        config = _make_phase2_config(workspace_root)
        channel = _IntegrationChannel(workspace_root)
        _register_roles(mock_substrate)

        runtime = PipelineRuntime(sub=mock_substrate, config=config)
        results = _drive_full_pipeline(runtime, channel)

        for key in ("interface_spec", "test_suite", "implementation"):
            wi = results[key]
            events = mock_substrate.read_events(work_item_id=wi.work_item_id)
            transitions = [e.transition for e in events]
            assert "claim" in transitions, f"{key}: missing claim"
            assert "submit" in transitions, f"{key}: missing submit"
            assert "gate_pass" in transitions, f"{key}: missing gate_pass"

    def test_artifact_paths_propagate_through_chain(self, mock_substrate, workspace_root):
        mock_substrate.register_workflow_file(
            str(Path(__file__).parent.parent / "workflows" / "phase2.yaml")
        )
        config = _make_phase2_config(workspace_root)
        channel = _IntegrationChannel(workspace_root)
        _register_roles(mock_substrate)

        runtime = PipelineRuntime(sub=mock_substrate, config=config)
        results = _drive_full_pipeline(runtime, channel)

        # Each item should have an artifact_path after submission
        for key in ("interface_spec", "test_suite", "implementation"):
            wi = mock_substrate.get_work_item(results[key].work_item_id)
            artifact_path = (wi.custom_fields or {}).get("artifact_path", "")
            assert artifact_path, f"{key}: no artifact_path"
            assert Path(artifact_path).exists(), f"{key}: artifact file missing at {artifact_path}"

        # test_suite should carry interface_ref pointing to the interface_spec
        ts = mock_substrate.get_work_item(results["test_suite"].work_item_id)
        assert (ts.custom_fields or {}).get("interface_ref") == str(
            results["interface_spec"].work_item_id,
        )

        # implementation should carry both refs
        impl = mock_substrate.get_work_item(results["implementation"].work_item_id)
        assert (impl.custom_fields or {}).get("interface_ref") == str(
            results["interface_spec"].work_item_id,
        )
        assert (impl.custom_fields or {}).get("test_suite_ref") == str(
            results["test_suite"].work_item_id,
        )

    def test_e2e_escalation_through_repeated_gate_failures(self, mock_substrate, workspace_root):
        mock_substrate.register_workflow_file(
            str(Path(__file__).parent.parent / "workflows" / "phase2.yaml")
        )
        config = _make_phase2_config(workspace_root)
        channel = _BadImplIntegrationChannel(workspace_root)
        _register_roles(mock_substrate)

        runtime = PipelineRuntime(sub=mock_substrate, config=config)

        iface, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={"spec_section": "def compute(x: int) -> str", "ac_ids": ["AC-01"]},
        )

        wi = _run_worker_stage(
            runtime,
            channel,
            iface,
            "factory-arch",
            "interface_architect",
        )
        wi = _run_gate(runtime, wi)
        assert wi.current_state == "locked"

        ts_wi = _create_downstream(runtime, wi, "interface_spec", "locked")
        wi = _run_worker_stage(
            runtime,
            channel,
            ts_wi,
            "factory-tester",
            "test_author",
        )
        wi = _run_gate(runtime, wi)
        assert wi.current_state == "locked"

        impl_wi = _create_downstream(runtime, wi, "test_suite", "locked")
        assert impl_wi is not None

        # Attempt 1: worker produces bad artifact (bare except), gate fails impl_lint
        # Worker claim=attempt1, Gate claim=attempt2. attempt2 < 3, normal gate_fail.
        wi = _run_worker_stage(
            runtime,
            channel,
            impl_wi,
            "factory-impl",
            "implementer",
        )
        assert wi.current_state == "gating"
        wi = _run_gate(runtime, wi)
        assert wi.current_state == "new"
        diags = (wi.custom_fields or {}).get("diagnostics", {})
        assert diags.get("diagnostic_kind") == "impl_lint"

        # Attempt 2: worker sees prior gate_fail so does NOT resume; invokes channel again,
        # produces another bad artifact, gate fails impl_lint again.
        # Worker claim=attempt3, Gate claim=attempt4. attempt4 >= 3, escalation fires.
        # Item transitions to cannot_proceed (terminal), stopping the retry loop.
        impl_wi = mock_substrate.get_work_item(impl_wi.work_item_id)
        wi = _run_worker_stage(
            runtime,
            channel,
            impl_wi,
            "factory-impl",
            "implementer",
        )
        assert wi.current_state == "gating"
        wi = _run_gate(runtime, wi)
        assert wi.current_state == "cannot_proceed"
        diags = (wi.custom_fields or {}).get("diagnostics", {})
        assert diags.get("diagnostic_kind") == "cannot_proceed_seam"
        assert diags.get("escalated_from_kind") == "impl_lint"
        assert diags.get("escalated_after_attempts") == 4

        impl_events = mock_substrate.read_events(work_item_id=impl_wi.work_item_id)
        gate_fails = [e for e in impl_events if e.transition == "gate_fail"]
        assert len(gate_fails) == 1
        gate_escalations = [e for e in impl_events if e.transition == "gate_escalation"]
        assert len(gate_escalations) == 1
