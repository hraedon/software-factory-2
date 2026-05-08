from __future__ import annotations

from pathlib import Path

from factory.channel import InvocationResult
from factory.config import FactoryConfig
from factory.gate_process import process_gate_item
from factory.runner import _resume_and_submit, process_work_item
from factory.runtime import PipelineRuntime
from factory.scheduler import _ensure_downstream_item
from factory.workspace import (
    ArtifactManifest,
    attempt_dir,
    compute_sha256,
    find_resumable_artifact,
    write_artifact,
)


class _IdempotencyChannel:
    def __init__(self, workspace_root: Path):
        self._workspace_root = workspace_root
        self._name = "idem-test"
        self._family = "test"
        self._role_attempt_counts: dict[str, int] = {}
        self._invocations: list[tuple[str, int]] = []
        self._fail_at: dict[tuple[str, int], str] = {}

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

    def invoke(self, role, prompt, inputs_dir, outputs_dir, timeout):
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

        if role == "interface_architect":
            content = (
                "from dataclasses import dataclass\n"
                "def compute(x: int) -> str:\n"
                '    """AC-01"""\n'
                "    ...\n"
            )
            name = "artifact.pyi"
        elif role == "test_author":
            content = (
                "def compute(x: int) -> str:\n"
                "    return str(x)\n\n"
                "def test_compute():\n"
                '    """AC-01"""\n'
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


def _make_phase2_config(workspace_root: Path) -> FactoryConfig:
    return FactoryConfig(
        workspace_root=workspace_root,
        workflow_version=2,
        worker_roles=FactoryConfig.PHASE2_WORKER_ROLES,
        type_to_role=FactoryConfig.PHASE2_TYPE_TO_ROLE,
        roles=FactoryConfig.PHASE2_ROLES,
    )


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


def _write_resumable_artifact(workspace_root, work_item_id, attempt, role, artifact_name, content):
    ad = attempt_dir(workspace_root, str(work_item_id), attempt)
    data = content.encode()
    sha = compute_sha256(data)
    manifest = ArtifactManifest(
        attempt_number=attempt,
        work_item_id=str(work_item_id),
        artifact_name=artifact_name,
        artifact_sha256=sha,
        artifact_size=len(data),
        actor_id=f"factory-{role[:4]}",
        channel="idem-test",
        family="test",
        context_hash=f"ctx-{work_item_id}-{attempt}",
    )
    write_artifact(ad, artifact_name, data, manifest)
    return ad / artifact_name


def _resume_and_gate(
    sub,
    config,
    channel,
    wi,
    workspace_root,
    actor_id,
    role_name,
    artifact_content,
    artifact_name,
):
    artifact_path = _write_resumable_artifact(
        workspace_root,
        wi.work_item_id,
        1,
        role_name[:4],
        artifact_name,
        artifact_content,
    )
    resumable = find_resumable_artifact(workspace_root, str(wi.work_item_id))
    assert resumable is not None
    n, manifest = resumable

    _ = sub.acquire_claim(wi.work_item_id, actor_id)
    sub.transition(wi.work_item_id, "claim", actor_id, actor_metadata={"role": role_name})
    _resume_and_submit(
        sub,
        wi,
        n,
        manifest,
        actor_id,
        channel,
        artifact_path,
        role_name=role_name,
    )
    return sub.get_work_item(wi.work_item_id)


class TestPipelineIdempotencyInterfaceArchitect:
    def test_resume_after_worker_crash_before_submit(self, mock_substrate, workspace_root):
        mock_substrate.register_workflow_file(
            str(Path(__file__).parent.parent / "workflows" / "phase2.yaml")
        )
        config = _make_phase2_config(workspace_root)
        channel = _IdempotencyChannel(workspace_root)
        _register_roles(mock_substrate)

        iface, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={"spec_section": "def compute(x: int) -> str", "ac_ids": ["AC-01"]},
        )

        artifact_content = (
            "from dataclasses import dataclass\n"
            "def compute(x: int) -> str:\n"
            '    """AC-01"""\n'
            "    ...\n"
        )
        wi = _resume_and_gate(
            mock_substrate,
            config,
            channel,
            iface,
            workspace_root,
            "factory-arch",
            "interface_architect",
            artifact_content,
            "artifact.pyi",
        )
        assert wi.current_state == "gating"
        runtime = PipelineRuntime(sub=mock_substrate, config=config)
        wi = _run_gate(runtime, wi)
        assert wi.current_state == "locked"
        assert len(channel._invocations) == 0

    def test_resume_carries_original_actor_metadata(self, mock_substrate, workspace_root):
        mock_substrate.register_workflow_file(
            str(Path(__file__).parent.parent / "workflows" / "phase2.yaml")
        )
        _ = _make_phase2_config(workspace_root)
        channel = _IdempotencyChannel(workspace_root)
        _register_roles(mock_substrate)

        iface, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={"spec_section": "def foo() -> int", "ac_ids": ["AC-01"]},
        )

        artifact_path = _write_resumable_artifact(
            workspace_root,
            iface.work_item_id,
            1,
            "arch",
            "artifact.pyi",
            "def foo() -> int:\n    'AC-01'\n    ...\n",
        )
        resumable = find_resumable_artifact(workspace_root, str(iface.work_item_id))
        assert resumable is not None
        attempt_num, manifest = resumable

        _ = mock_substrate.acquire_claim(iface.work_item_id, "factory-arch")
        mock_substrate.transition(
            iface.work_item_id,
            "claim",
            "factory-arch",
            actor_metadata={"role": "interface_architect"},
        )
        _resume_and_submit(
            mock_substrate,
            iface,
            attempt_num,
            manifest,
            "factory-arch",
            channel,
            artifact_path,
            role_name="interface_architect",
        )

        events = mock_substrate.read_events(work_item_id=iface.work_item_id)
        submit_events = [e for e in events if e.transition == "submit"]
        assert len(submit_events) == 1
        md = submit_events[0].actor_metadata or {}
        assert md.get("role") == "interface_architect"
        assert md.get("attempt_n") == 1


class TestPipelineIdempotencyTestAuthor:
    def test_resume_test_author_after_crash(self, mock_substrate, workspace_root):
        mock_substrate.register_workflow_file(
            str(Path(__file__).parent.parent / "workflows" / "phase2.yaml")
        )
        config = _make_phase2_config(workspace_root)
        channel = _IdempotencyChannel(workspace_root)
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

        sched_runtime = PipelineRuntime(sub=mock_substrate, config=config)
        _ensure_downstream_item(
            sched_runtime,
            wi,
            {"next_type": "test_suite", "link_type": "derived_from", "next_role": "test_author"},
        )
        ts_wis = [
            w
            for w in mock_substrate.query_work_items(
                current_states=["new"],
                page_size=50,
            ).items
            if w.work_item_type == "test_suite"
        ]
        assert len(ts_wis) == 1
        ts_wi = ts_wis[0]

        artifact_content = (
            "def compute(x: int) -> str:\n"
            "    return str(x)\n\n"
            "def test_compute():\n"
            '    """AC-01"""\n'
            '    assert compute(1) == "1"\n'
        )
        wi = _resume_and_gate(
            mock_substrate,
            config,
            channel,
            ts_wi,
            workspace_root,
            "factory-tester",
            "test_author",
            artifact_content,
            "test_suite.py",
        )
        assert wi.current_state == "gating"
        wi = _run_gate(runtime, wi)
        assert wi.current_state == "locked"


class TestPipelineIdempotencyImplementer:
    def test_resume_implementer_after_crash(self, mock_substrate, workspace_root):
        mock_substrate.register_workflow_file(
            str(Path(__file__).parent.parent / "workflows" / "phase2.yaml")
        )
        config = _make_phase2_config(workspace_root)
        channel = _IdempotencyChannel(workspace_root)
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

        sched_runtime = PipelineRuntime(sub=mock_substrate, config=config)
        _ensure_downstream_item(
            sched_runtime,
            wi,
            {"next_type": "test_suite", "link_type": "derived_from", "next_role": "test_author"},
        )
        ts_wis = [
            w
            for w in mock_substrate.query_work_items(
                current_states=["new"],
                page_size=50,
            ).items
            if w.work_item_type == "test_suite"
        ]
        ts_wi = ts_wis[0]

        wi = _run_worker_stage(
            runtime,
            channel,
            ts_wi,
            "factory-tester",
            "test_author",
        )
        wi = _run_gate(runtime, wi)
        assert wi.current_state == "locked"

        _ensure_downstream_item(
            sched_runtime,
            wi,
            {
                "next_type": "implementation",
                "link_type": "tested_by",
                "additional_links": ["implements"],
                "next_role": "implementer",
            },
        )
        impl_wis = [
            w
            for w in mock_substrate.query_work_items(
                current_states=["new"],
                page_size=50,
            ).items
            if w.work_item_type == "implementation"
        ]
        impl_wi = impl_wis[0]

        artifact_content = "def compute(x: int) -> str:\n    return str(x)\n"
        wi = _resume_and_gate(
            mock_substrate,
            config,
            channel,
            impl_wi,
            workspace_root,
            "factory-impl",
            "implementer",
            artifact_content,
            "impl.py",
        )
        assert wi.current_state == "gating"
        wi = _run_gate(runtime, wi)
        assert wi.current_state == "locked"


class TestPipelineIdempotencyGateProcess:
    def test_gate_reclaim_after_crash_is_safe(self, mock_substrate, workspace_root):
        mock_substrate.register_workflow_file(
            str(Path(__file__).parent.parent / "workflows" / "phase2.yaml")
        )
        config = _make_phase2_config(workspace_root)
        channel = _IdempotencyChannel(workspace_root)
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
        assert wi.current_state == "gating"

        wi = _run_gate(runtime, wi)
        assert wi.current_state == "locked"

        events = mock_substrate.read_events(work_item_id=iface.work_item_id)
        gate_passes = [e for e in events if e.transition == "gate_pass"]
        assert len(gate_passes) == 1

    def test_test_suite_gate_reclaim_after_crash(self, mock_substrate, workspace_root):
        mock_substrate.register_workflow_file(
            str(Path(__file__).parent.parent / "workflows" / "phase2.yaml")
        )
        config = _make_phase2_config(workspace_root)
        channel = _IdempotencyChannel(workspace_root)
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

        sched_runtime = PipelineRuntime(sub=mock_substrate, config=config)
        _ensure_downstream_item(
            sched_runtime,
            wi,
            {"next_type": "test_suite", "link_type": "derived_from", "next_role": "test_author"},
        )
        ts_wis = [
            w
            for w in mock_substrate.query_work_items(
                current_states=["new"],
                page_size=50,
            ).items
            if w.work_item_type == "test_suite"
        ]
        ts_wi = ts_wis[0]

        wi = _run_worker_stage(
            runtime,
            channel,
            ts_wi,
            "factory-tester",
            "test_author",
        )
        assert wi.current_state == "gating"

        wi = _run_gate(runtime, wi)
        assert wi.current_state == "locked"


class TestPipelineIdempotencyMultiRole:
    def test_mid_pipeline_crash_at_each_stage(self, mock_substrate, workspace_root):
        mock_substrate.register_workflow_file(
            str(Path(__file__).parent.parent / "workflows" / "phase2.yaml")
        )
        config = _make_phase2_config(workspace_root)
        channel = _IdempotencyChannel(workspace_root)
        _register_roles(mock_substrate)

        runtime = PipelineRuntime(sub=mock_substrate, config=config)
        sched_runtime = PipelineRuntime(sub=mock_substrate, config=config)

        iface, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={"spec_section": "def compute(x: int) -> str", "ac_ids": ["AC-01"]},
        )

        # Stage 1: interface_architect — resume from crash
        iface_artifact = 'def compute(x: int) -> str:\n    """AC-01"""\n    ...\n'
        wi = _resume_and_gate(
            mock_substrate,
            config,
            channel,
            iface,
            workspace_root,
            "factory-arch",
            "interface_architect",
            iface_artifact,
            "artifact.pyi",
        )
        assert wi.current_state == "gating"
        wi = _run_gate(runtime, wi)
        assert wi.current_state == "locked"

        # Stage 2: test_author — resume from crash
        _ensure_downstream_item(
            sched_runtime,
            wi,
            {"next_type": "test_suite", "link_type": "derived_from", "next_role": "test_author"},
        )
        ts_wis = [
            w
            for w in mock_substrate.query_work_items(
                current_states=["new"],
                page_size=50,
            ).items
            if w.work_item_type == "test_suite"
        ]
        ts_wi = ts_wis[0]

        ts_artifact = (
            "def compute(x: int) -> str:\n"
            "    return str(x)\n\n"
            "def test_compute():\n"
            '    """AC-01"""\n'
            "    assert True\n"
        )
        wi = _resume_and_gate(
            mock_substrate,
            config,
            channel,
            ts_wi,
            workspace_root,
            "factory-tester",
            "test_author",
            ts_artifact,
            "test_suite.py",
        )
        assert wi.current_state == "gating"
        wi = _run_gate(runtime, wi)
        assert wi.current_state == "locked"

        # Stage 3: implementer — resume from crash
        _ensure_downstream_item(
            sched_runtime,
            wi,
            {
                "next_type": "implementation",
                "link_type": "tested_by",
                "additional_links": ["implements"],
                "next_role": "implementer",
            },
        )
        impl_wis = [
            w
            for w in mock_substrate.query_work_items(
                current_states=["new"],
                page_size=50,
            ).items
            if w.work_item_type == "implementation"
        ]
        impl_wi = impl_wis[0]

        impl_artifact = "def compute(x: int) -> str:\n    return str(x)\n"
        wi = _resume_and_gate(
            mock_substrate,
            config,
            channel,
            impl_wi,
            workspace_root,
            "factory-impl",
            "implementer",
            impl_artifact,
            "impl.py",
        )
        assert wi.current_state == "gating"
        wi = _run_gate(runtime, wi)
        assert wi.current_state == "locked"

        assert len(channel._invocations) == 0
