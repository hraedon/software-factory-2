from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from regista._testing import drop_project_schema

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

TESTS_DIR = Path(__file__).parent
DSN = "postgresql://regista_test:regista_test@localhost:5432/regista_test"
KEY_PATH = str(TESTS_DIR / "test_keys.json")
PHASE2_PATH = str(Path(__file__).parent.parent / "workflows" / "phase2.yaml")

_IFACE_TO_TEST_SUITE = StageHandoff(
    source_type=WORK_ITEM_TYPE_INTERFACE_SPEC,
    source_state="locked",
    target_type=WORK_ITEM_TYPE_TEST_SUITE,
    link_type=LINK_TYPE_DERIVED_FROM,
    ref_field=CUSTOM_FIELD_INTERFACE_REF,
)

_TEST_SUITE_TO_IMPL = StageHandoff(
    source_type=WORK_ITEM_TYPE_TEST_SUITE,
    source_state="locked",
    target_type=WORK_ITEM_TYPE_IMPLEMENTATION,
    link_type=LINK_TYPE_TESTED_BY,
    additional_links=("implements",),
    ref_field=CUSTOM_FIELD_TEST_SUITE_REF,
    propagate_fields=(CUSTOM_FIELD_INTERFACE_REF,),
)


class _StubChannel:
    def __init__(self, workspace_root: Path):
        self._workspace_root = workspace_root
        self._name = "stub"
        self._family = "test"

    @property
    def name(self) -> str:
        return self._name

    @property
    def family(self) -> str:
        return self._family

    def invoke(self, role, prompt, outputs_dir, timeout, extra_env=None):
        outputs_dir.mkdir(parents=True, exist_ok=True)
        if role == "interface_architect":
            content = 'def compute(x: int) -> str:\n    """AC-01"""\n    ...\n'
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


@pytest.fixture(scope="module")
def real_sub():
    from regista import Regista

    project = f"sf2_integ_{uuid.uuid4().hex[:8]}"
    sub = Regista.create_project(DSN, project, KEY_PATH)
    sub.register_workflow_file(PHASE2_PATH)
    yield sub
    sub.close()
    drop_project_schema(DSN, project)


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
    rt = PipelineRuntime(
        sub=runtime.sub,
        config=runtime.config,
        spec_content=spec_content,
        channel=channel,
    )
    process_work_item(rt, wi, actor_id, claim, role_name)
    return runtime.sub.get_work_item(wi.work_item_id)


def _run_gate(runtime, wi, actor_id="factory-gate"):
    claim = runtime.sub.acquire_claim(wi.work_item_id, actor_id)
    rt = PipelineRuntime(sub=runtime.sub, config=runtime.config)
    process_gate_item(rt, wi, actor_id, claim)
    return runtime.sub.get_work_item(wi.work_item_id)


def _write_resumable(workspace_root, work_item_id, attempt, artifact_name, content):
    ad = attempt_dir(workspace_root, str(work_item_id), attempt)
    data = content.encode()
    sha = compute_sha256(data)
    manifest = ArtifactManifest(
        attempt_number=attempt,
        work_item_id=str(work_item_id),
        artifact_name=artifact_name,
        artifact_sha256=sha,
        artifact_size=len(data),
        actor_id="factory-arch",
        channel="stub",
        family="test",
        context_hash=f"ctx-{work_item_id}-{attempt}",
    )
    write_artifact(ad, artifact_name, data, manifest)
    return ad / artifact_name


@pytest.mark.integration
class TestTestSuiteLifecycle:
    def test_test_suite_claim_submit_gate_pass_on_real_regista(self, real_sub, tmp_path):
        _register_roles(real_sub)
        config = FactoryConfig.phase2(workspace_root=tmp_path / "work")
        channel = _StubChannel(tmp_path / "work")
        runtime = PipelineRuntime(sub=real_sub, config=config)

        iface, _ = real_sub.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="factory-arch",
            custom_fields={"spec_section": "def compute(x: int) -> str", "ac_ids": ["AC-01"]},
        )
        iface = _run_worker_stage(runtime, channel, iface, "factory-arch", "interface_architect")
        iface = _run_gate(runtime, iface)
        assert iface.current_state == "locked"

        sched_rt = PipelineRuntime(sub=real_sub, config=config)
        _ensure_downstream_item(sched_rt, iface, _IFACE_TO_TEST_SUITE)
        ts_wis = [
            w
            for w in real_sub.query_work_items(
                current_states=["new"],
                page_size=50,
            ).items
            if w.work_item_type == "test_suite"
        ]
        assert len(ts_wis) == 1
        ts_wi = ts_wis[0]
        assert ts_wi.custom_fields.get(CUSTOM_FIELD_INTERFACE_REF) == str(iface.work_item_id)

        ts_result = _run_worker_stage(runtime, channel, ts_wi, "factory-tester", "test_author")
        assert ts_result.current_state == "gating"

        ts_result = _run_gate(runtime, ts_result)
        assert ts_result.current_state == "locked"

    def test_test_suite_gate_fail_returns_to_new_on_real_regista(self, real_sub, tmp_path):
        _register_roles(real_sub)
        config = FactoryConfig.phase2(workspace_root=tmp_path / "work2")
        runtime = PipelineRuntime(sub=real_sub, config=config)

        iface, _ = real_sub.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="factory-arch",
            custom_fields={"spec_section": "def foo() -> int", "ac_ids": ["AC-01"]},
        )
        real_sub.transition(
            iface.work_item_id,
            "claim",
            "factory-arch",
            actor_metadata={"role": "interface_architect"},
        )
        real_sub.transition(
            iface.work_item_id,
            "submit",
            "factory-arch",
            actor_metadata={"role": "interface_architect"},
            custom_fields={"artifact_path": "", "artifact_hash": "abc"},
        )
        claim = real_sub.acquire_claim(iface.work_item_id, "factory-gate")
        fresh = real_sub.get_work_item(iface.work_item_id)
        process_gate_item(runtime, fresh, "factory-gate", claim)
        iface = real_sub.get_work_item(iface.work_item_id)
        assert iface.current_state == "new"


@pytest.mark.integration
class TestImplementationLifecycle:
    def test_implementation_full_chain_on_real_regista(self, real_sub, tmp_path):
        _register_roles(real_sub)
        config = FactoryConfig.phase2(workspace_root=tmp_path / "work3")
        channel = _StubChannel(tmp_path / "work3")
        runtime = PipelineRuntime(sub=real_sub, config=config)
        sched_rt = PipelineRuntime(sub=real_sub, config=config)

        iface, _ = real_sub.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="factory-arch",
            custom_fields={"spec_section": "def compute(x: int) -> str", "ac_ids": ["AC-01"]},
        )
        iface = _run_worker_stage(runtime, channel, iface, "factory-arch", "interface_architect")
        iface = _run_gate(runtime, iface)
        assert iface.current_state == "locked"

        _ensure_downstream_item(sched_rt, iface, _IFACE_TO_TEST_SUITE)
        ts_wis = [
            w
            for w in real_sub.query_work_items(
                current_states=["new"],
                page_size=50,
            ).items
            if w.work_item_type == "test_suite"
        ]
        ts_wi = ts_wis[0]
        ts_result = _run_worker_stage(runtime, channel, ts_wi, "factory-tester", "test_author")
        ts_result = _run_gate(runtime, ts_result)
        assert ts_result.current_state == "locked"

        _ensure_downstream_item(sched_rt, ts_result, _TEST_SUITE_TO_IMPL)
        impl_wis = [
            w
            for w in real_sub.query_work_items(
                current_states=["new"],
                page_size=50,
            ).items
            if w.work_item_type == "implementation"
        ]
        assert len(impl_wis) == 1
        impl_wi = impl_wis[0]
        assert impl_wi.custom_fields.get(CUSTOM_FIELD_INTERFACE_REF) == str(iface.work_item_id)
        assert impl_wi.custom_fields.get(CUSTOM_FIELD_TEST_SUITE_REF) == str(ts_wi.work_item_id)

        impl_result = _run_worker_stage(runtime, channel, impl_wi, "factory-impl", "implementer")
        assert impl_result.current_state == "gating"
        impl_result = _run_gate(runtime, impl_result)
        assert impl_result.current_state == "locked"


@pytest.mark.integration
class TestSchedulerDAGCreation:
    def test_scheduler_creates_downstream_after_lock(self, real_sub, tmp_path):
        _register_roles(real_sub)
        config = FactoryConfig.phase2(workspace_root=tmp_path / "work4")
        runtime = PipelineRuntime(sub=real_sub, config=config)

        iface, _ = real_sub.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="factory-arch",
            custom_fields={"spec_section": "def bar() -> str", "ac_ids": ["AC-01"]},
        )
        real_sub.transition(
            iface.work_item_id,
            "claim",
            "factory-arch",
            actor_metadata={"role": "interface_architect"},
        )
        real_sub.transition(
            iface.work_item_id,
            "submit",
            "factory-arch",
            actor_metadata={"role": "interface_architect"},
            custom_fields={"artifact_path": "/dev/null", "artifact_hash": "x"},
        )
        real_sub.transition(
            iface.work_item_id,
            "gate_pass",
            "factory-gate",
            actor_metadata={"role": "mechanical_gate"},
        )
        assert real_sub.get_work_item(iface.work_item_id).current_state == "locked"

        _ensure_downstream_item(runtime, iface, _IFACE_TO_TEST_SUITE)

        ts_wis = [
            w
            for w in real_sub.query_work_items(
                current_states=["new"],
                page_size=50,
            ).items
            if w.work_item_type == "test_suite"
            and (w.custom_fields or {}).get(CUSTOM_FIELD_INTERFACE_REF) == str(iface.work_item_id)
        ]
        assert len(ts_wis) == 1

    def test_scheduler_idempotent_on_repeated_calls(self, real_sub, tmp_path):
        _register_roles(real_sub)
        config = FactoryConfig.phase2(workspace_root=tmp_path / "work5")
        runtime = PipelineRuntime(sub=real_sub, config=config)

        iface, _ = real_sub.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="factory-arch",
            custom_fields={"spec_section": "def baz() -> int", "ac_ids": ["AC-01"]},
        )
        real_sub.transition(
            iface.work_item_id,
            "claim",
            "factory-arch",
            actor_metadata={"role": "interface_architect"},
        )
        real_sub.transition(
            iface.work_item_id,
            "submit",
            "factory-arch",
            actor_metadata={"role": "interface_architect"},
            custom_fields={"artifact_path": "/dev/null", "artifact_hash": "x"},
        )
        real_sub.transition(
            iface.work_item_id,
            "gate_pass",
            "factory-gate",
            actor_metadata={"role": "mechanical_gate"},
        )

        _ensure_downstream_item(runtime, iface, _IFACE_TO_TEST_SUITE)
        _ensure_downstream_item(runtime, iface, _IFACE_TO_TEST_SUITE)

        ts_wis = [
            w
            for w in real_sub.query_work_items(
                current_states=["new"],
                page_size=50,
            ).items
            if w.work_item_type == "test_suite"
            and (w.custom_fields or {}).get(CUSTOM_FIELD_INTERFACE_REF) == str(iface.work_item_id)
        ]
        assert len(ts_wis) == 1


@pytest.mark.integration
class TestChannelFailureRetry:
    def test_channel_fail_returns_to_new_and_reclaimable(self, real_sub, tmp_path):
        _register_roles(real_sub)

        wi, _ = real_sub.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="factory-arch",
            custom_fields={"spec_section": "def qux() -> bool", "ac_ids": ["AC-01"]},
        )
        real_sub.transition(
            wi.work_item_id,
            "claim",
            "factory-arch",
            actor_metadata={"role": "interface_architect"},
        )
        assert real_sub.get_work_item(wi.work_item_id).current_state == "in_progress"

        real_sub.transition(
            wi.work_item_id,
            "channel_fail",
            "factory-arch",
            actor_metadata={"role": "interface_architect"},
            payload={"diagnostics": {"error_message": "timeout", "timed_out": True}},
        )
        assert real_sub.get_work_item(wi.work_item_id).current_state == "new"

        real_sub.transition(
            wi.work_item_id,
            "claim",
            "factory-arch",
            actor_metadata={"role": "interface_architect"},
        )
        assert real_sub.get_work_item(wi.work_item_id).current_state == "in_progress"

    def test_channel_fail_events_recorded_in_order(self, real_sub, tmp_path):
        _register_roles(real_sub)

        wi, _ = real_sub.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="factory-arch",
            custom_fields={"spec_section": "def event_test() -> None", "ac_ids": ["AC-01"]},
        )
        real_sub.transition(
            wi.work_item_id,
            "claim",
            "factory-arch",
            actor_metadata={"role": "interface_architect"},
        )
        real_sub.transition(
            wi.work_item_id,
            "channel_fail",
            "factory-arch",
            actor_metadata={"role": "interface_architect"},
            payload={"diagnostics": {"error_message": "empty output"}},
        )
        real_sub.transition(
            wi.work_item_id,
            "claim",
            "factory-arch",
            actor_metadata={"role": "interface_architect"},
        )

        events = real_sub.read_events(work_item_id=wi.work_item_id)
        transitions = [e.transition for e in events]
        assert "claim" in transitions
        assert "channel_fail" in transitions
        claim_indices = [i for i, t in enumerate(transitions) if t == "claim"]
        fail_indices = [i for i, t in enumerate(transitions) if t == "channel_fail"]
        assert len(claim_indices) == 2
        assert len(fail_indices) == 1
        assert claim_indices[0] < fail_indices[0] < claim_indices[1]


@pytest.mark.integration
class TestCrashRecoveryResume:
    def test_resume_interface_spec_after_crash_on_real_regista(self, real_sub, tmp_path):
        _register_roles(real_sub)
        config = FactoryConfig.phase2(workspace_root=tmp_path / "work6")
        channel = _StubChannel(tmp_path / "work6")
        workspace_root = tmp_path / "work6"

        iface, _ = real_sub.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="factory-arch",
            custom_fields={"spec_section": "def resumed() -> int", "ac_ids": ["AC-01"]},
        )

        artifact_content = 'def resumed() -> int:\n    """AC-01"""\n    ...\n'
        artifact_path = _write_resumable(
            workspace_root,
            iface.work_item_id,
            1,
            "artifact.pyi",
            artifact_content,
        )
        resumable = find_resumable_artifact(workspace_root, str(iface.work_item_id))
        assert resumable is not None
        attempt_num, manifest = resumable

        real_sub.acquire_claim(iface.work_item_id, "factory-arch")
        real_sub.transition(
            iface.work_item_id,
            "claim",
            "factory-arch",
            actor_metadata={"role": "interface_architect"},
        )
        _resume_and_submit(
            real_sub,
            iface,
            attempt_num,
            manifest,
            "factory-arch",
            channel,
            artifact_path,
            role_name="interface_architect",
        )
        wi = real_sub.get_work_item(iface.work_item_id)
        assert wi.current_state == "gating"

        runtime = PipelineRuntime(sub=real_sub, config=config)
        wi = _run_gate(runtime, wi)
        assert wi.current_state == "locked"
