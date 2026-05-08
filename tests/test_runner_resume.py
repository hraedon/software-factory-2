from __future__ import annotations

from factory.channel import InvocationResult
from factory.config import FactoryConfig
from factory.gate_process import process_gate_item
from factory.runner import process_work_item
from factory.runtime import PipelineRuntime
from factory.workspace import (
    ArtifactManifest,
    attempt_dir,
    compute_sha256,
    write_artifact,
)
from tests._helpers import events_by_transition


class _FakeChannel:
    """Channel that records invocations but always succeeds."""

    def __init__(self, ac_ids: list[str] | None = None):
        self._name = "fake"
        self._family = "test"
        self._ac_ids = ac_ids or []
        self._invocations: list[tuple[str, str, object, object]] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def family(self) -> str:
        return self._family

    def invoke(self, role, prompt, inputs_dir, outputs_dir, timeout):
        self._invocations.append((role, prompt, inputs_dir, outputs_dir))
        outputs_dir.mkdir(parents=True, exist_ok=True)
        ac_doc = ", ".join(self._ac_ids) if self._ac_ids else "AC-01"
        content = f'def foo(x: int) -> str:\n    """Satisfies {ac_doc}."""\n    ...\n'
        (outputs_dir / "artifact.pyi").write_text(content)
        return InvocationResult(success=True, artifact_name="artifact.pyi")

    @property
    def was_invoked(self) -> bool:
        return len(self._invocations) > 0


class TestResumeAndSubmit:
    def test_resumes_without_invoking_channel(self, mock_substrate, workspace_root):
        """BC-014: If a valid resumable artifact exists, the channel must NOT be invoked."""
        wi, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={"spec_section": "Resume test", "ac_ids": ["AC-01"]},
        )
        mock_substrate.register_actor_role("test-worker", "interface_architect")

        claim = mock_substrate.acquire_claim(wi.work_item_id, "test-worker")
        mock_substrate.transition(
            wi.work_item_id,
            "claim",
            "test-worker",
            actor_metadata={"role": "interface_architect"},
        )

        # Pre-seed a valid artifact+manifest in the workspace
        data = b'def resume_func(x: int) -> str:\n    """Satisfies AC-01."""\n    ...\n'
        sha = compute_sha256(data)
        manifest = ArtifactManifest(
            attempt_number=1,
            work_item_id=str(wi.work_item_id),
            artifact_name="artifact.pyi",
            artifact_sha256=sha,
            artifact_size=len(data),
            channel="claude-code",
            family="anthropic",
            context_hash="ctx-resume-001",
        )
        ad = attempt_dir(workspace_root, str(wi.work_item_id), 1)
        write_artifact(ad, "artifact.pyi", data, manifest)

        config = FactoryConfig(workspace_root=workspace_root)
        channel = _FakeChannel(ac_ids=["AC-01"])
        runtime = PipelineRuntime(
            sub=mock_substrate, config=config, spec_content="Resume test", channel=channel
        )
        process_work_item(
            runtime,
            wi,
            "test-worker",
            claim,
            "interface_architect",
        )

        # Channel must not have been invoked
        assert not channel.was_invoked, (
            "Channel was invoked even though a resumable artifact existed"
        )

        # Work-item must be in gating
        updated = mock_substrate.get_work_item(wi.work_item_id)
        assert updated.current_state == "gating"

        # artifact_path in custom_fields must be a full absolute path
        artifact_path = updated.custom_fields.get("artifact_path", "")
        assert artifact_path.startswith("/")
        assert artifact_path.endswith("artifact.pyi")

    def test_gate_finds_resumed_artifact_and_transitions_to_locked(
        self, mock_substrate, workspace_root
    ):
        """BC-014: Gate must find the artifact at the resumed path and lock the item."""
        wi, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={"spec_section": "Gate resume test", "ac_ids": ["AC-01"]},
        )
        mock_substrate.register_actor_role("test-worker", "interface_architect")
        claim = mock_substrate.acquire_claim(wi.work_item_id, "test-worker")
        mock_substrate.transition(
            wi.work_item_id,
            "claim",
            "test-worker",
            actor_metadata={"role": "interface_architect"},
        )

        data = b'def gate_resume(x: str) -> int:\n    """Satisfies AC-01."""\n    ...\n'
        sha = compute_sha256(data)
        manifest = ArtifactManifest(
            attempt_number=1,
            work_item_id=str(wi.work_item_id),
            artifact_name="artifact.pyi",
            artifact_sha256=sha,
            artifact_size=len(data),
            channel="claude-code",
            family="anthropic",
            context_hash="ctx-resume-002",
        )
        ad = attempt_dir(workspace_root, str(wi.work_item_id), 1)
        write_artifact(ad, "artifact.pyi", data, manifest)

        config = FactoryConfig(workspace_root=workspace_root)
        channel = _FakeChannel(ac_ids=["AC-01"])
        runtime = PipelineRuntime(
            sub=mock_substrate, config=config, spec_content="Gate resume test", channel=channel
        )
        process_work_item(
            runtime,
            wi,
            "test-worker",
            claim,
            "interface_architect",
        )

        submitted = mock_substrate.get_work_item(wi.work_item_id)
        assert submitted.current_state == "gating"

        mock_substrate.register_actor_role("test-gate", "mechanical_gate")
        gate_claim = mock_substrate.acquire_claim(wi.work_item_id, "test-gate")
        fresh = mock_substrate.get_work_item(wi.work_item_id)
        gate_runtime = PipelineRuntime(sub=mock_substrate, config=config)
        process_gate_item(gate_runtime, fresh, "test-gate", gate_claim)

        final = mock_substrate.get_work_item(wi.work_item_id)
        assert final.current_state == "locked"

    def test_resume_preserves_actor_metadata(self, mock_substrate, workspace_root):
        """BC-014: Resumed artifact's original actor metadata is preserved in submit transition."""
        wi, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={"spec_section": "Metadata test", "ac_ids": ["AC-01"]},
        )
        mock_substrate.register_actor_role("test-worker", "interface_architect")
        claim = mock_substrate.acquire_claim(wi.work_item_id, "test-worker")
        mock_substrate.transition(
            wi.work_item_id,
            "claim",
            "test-worker",
            actor_metadata={"role": "interface_architect"},
        )

        data = b"def meta_test() -> None: ...\n"
        sha = compute_sha256(data)
        manifest = ArtifactManifest(
            attempt_number=1,
            work_item_id=str(wi.work_item_id),
            artifact_name="artifact.pyi",
            artifact_sha256=sha,
            artifact_size=len(data),
            channel="glm-5.1",
            family="zhipu",
            context_hash="ctx-meta-003",
        )
        ad = attempt_dir(workspace_root, str(wi.work_item_id), 1)
        write_artifact(ad, "artifact.pyi", data, manifest)

        config = FactoryConfig(workspace_root=workspace_root)
        channel = _FakeChannel()
        runtime = PipelineRuntime(
            sub=mock_substrate, config=config, spec_content="Metadata test", channel=channel
        )
        process_work_item(
            runtime,
            wi,
            "test-worker",
            claim,
            "interface_architect",
        )

        all_events = mock_substrate.read_events(work_item_id=wi.work_item_id)
        events = events_by_transition(all_events, "submit")
        assert len(events) == 1
        meta = events[0].actor_metadata or {}
        assert meta.get("channel") == "glm-5.1"
        assert meta.get("family") == "zhipu"
        assert meta.get("context_hash") == "ctx-meta-003"
