from __future__ import annotations

import json

from factory.channel import InvocationResult
from factory.config import FactoryConfig
from factory.runner import process_work_item
from factory.runtime import PipelineRuntime
from factory.workspace import (
    ArtifactManifest,
    attempt_dir,
    compute_sha256,
    write_artifact,
)
from tests._helpers import events_by_transition


class _FailingChannel:
    """Channel that returns configurable failure modes."""

    def __init__(self, result: InvocationResult):
        self._result = result
        self._name = "failing"
        self._family = "test"
        self._invocations: list = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def family(self) -> str:
        return self._family

    def invoke(self, role, prompt, inputs_dir, outputs_dir, timeout):
        self._invocations.append((role, prompt, inputs_dir, outputs_dir))
        return self._result


class TestRunnerInvokeFailure:
    def test_timeout_records_channel_fail_event(self, mock_substrate, workspace_root):
        wi, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={"spec_section": "Timeout test", "ac_ids": ["AC-01"]},
        )
        mock_substrate.register_actor_role("test-worker", "interface_architect")
        claim = mock_substrate.acquire_claim(wi.work_item_id, "test-worker")
        mock_substrate.transition(
            wi.work_item_id,
            "claim",
            "test-worker",
            actor_metadata={"role": "interface_architect"},
        )

        channel = _FailingChannel(
            InvocationResult(
                success=False,
                error_message="Timeout after 600s",
                exit_code=None,
                timed_out=True,
            )
        )
        config = FactoryConfig(workspace_root=workspace_root)
        runtime = PipelineRuntime(
            sub=mock_substrate, config=config, spec_content="Timeout test", channel=channel
        )
        process_work_item(
            runtime,
            wi,
            "test-worker",
            claim,
            "interface_architect",
        )

        updated = mock_substrate.get_work_item(wi.work_item_id)
        assert updated.current_state == "new"
        assert updated.claimed_by is None

        all_events = mock_substrate.read_events(work_item_id=wi.work_item_id)
        events = events_by_transition(all_events, "channel_fail")
        assert len(events) == 1
        payload = events[0].payload or {}
        diagnostics = payload.get("diagnostics", {})
        assert diagnostics.get("error_message") == "Timeout after 600s"
        assert diagnostics.get("timed_out") is True

    def test_generic_error_records_channel_fail(self, mock_substrate, workspace_root):
        wi, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={"spec_section": "Error test", "ac_ids": ["AC-01"]},
        )
        mock_substrate.register_actor_role("test-worker", "interface_architect")
        claim = mock_substrate.acquire_claim(wi.work_item_id, "test-worker")
        mock_substrate.transition(
            wi.work_item_id,
            "claim",
            "test-worker",
            actor_metadata={"role": "interface_architect"},
        )

        channel = _FailingChannel(
            InvocationResult(
                success=False,
                error_message="claude returned non-zero exit",
                exit_code=1,
                timed_out=False,
            )
        )
        config = FactoryConfig(workspace_root=workspace_root)
        runtime = PipelineRuntime(
            sub=mock_substrate, config=config, spec_content="Error test", channel=channel
        )
        process_work_item(
            runtime,
            wi,
            "test-worker",
            claim,
            "interface_architect",
        )

        updated = mock_substrate.get_work_item(wi.work_item_id)
        assert updated.current_state == "new"
        all_events = mock_substrate.read_events(work_item_id=wi.work_item_id)
        events = events_by_transition(all_events, "channel_fail")
        assert len(events) == 1
        payload = events[0].payload or {}
        diagnostics = payload.get("diagnostics", {})
        assert diagnostics.get("exit_code") == 1

    def test_cannot_proceed_transition(self, mock_substrate, workspace_root):
        class _CannotProceedChannel:
            def __init__(self):
                self._name = "cp"
                self._family = "test"

            @property
            def name(self) -> str:
                return self._name

            @property
            def family(self) -> str:
                return self._family

            def invoke(self, role, prompt, inputs_dir, outputs_dir, timeout):
                outputs_dir.mkdir(parents=True, exist_ok=True)
                cp = {"status": "cannot_proceed", "reason": "ambiguous", "gaps": ["AC conflict"]}
                (outputs_dir / "cannot_proceed.json").write_text(json.dumps(cp))
                return InvocationResult(
                    success=False, artifact_name=None, error_message="cannot_proceed"
                )

        wi, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={"spec_section": "CP test", "ac_ids": ["AC-01"]},
        )
        mock_substrate.register_actor_role("test-worker", "interface_architect")
        claim = mock_substrate.acquire_claim(wi.work_item_id, "test-worker")
        mock_substrate.transition(
            wi.work_item_id,
            "claim",
            "test-worker",
            actor_metadata={"role": "interface_architect"},
        )

        config = FactoryConfig(workspace_root=workspace_root)
        runtime = PipelineRuntime(
            sub=mock_substrate,
            config=config,
            spec_content="CP test",
            channel=_CannotProceedChannel(),
        )
        process_work_item(
            runtime,
            wi,
            "test-worker",
            claim,
            "interface_architect",
        )

        updated = mock_substrate.get_work_item(wi.work_item_id)
        assert updated.current_state == "cannot_proceed"
        custom = updated.custom_fields or {}
        assert "diagnostics" in custom


class TestRunnerResumePath:
    def test_resume_from_prior_attempt(self, mock_substrate, workspace_root):
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

        data = b"def foo() -> int: ..."
        sha = compute_sha256(data)
        manifest = ArtifactManifest(
            attempt_number=1,
            work_item_id=str(wi.work_item_id),
            artifact_name="artifact.pyi",
            artifact_sha256=sha,
            artifact_size=len(data),
            actor_id="factory-worker-test",
            channel="claude-code",
            family="anthropic",
            context_hash="ctx-hash-1",
        )
        ad = attempt_dir(workspace_root, str(wi.work_item_id), 1)
        write_artifact(ad, "artifact.pyi", data, manifest)

        class _NoOpChannel:
            @property
            def name(self) -> str:
                return "noop"

            @property
            def family(self) -> str:
                return "test"

            def invoke(self, *args, **kwargs):
                raise RuntimeError("should not be called when resuming")

        config = FactoryConfig(workspace_root=workspace_root)
        runtime = PipelineRuntime(
            sub=mock_substrate, config=config, spec_content="Resume test", channel=_NoOpChannel()
        )
        process_work_item(
            runtime,
            wi,
            "test-worker",
            claim,
            "interface_architect",
        )

        updated = mock_substrate.get_work_item(wi.work_item_id)
        assert updated.current_state == "gating"
        custom = updated.custom_fields or {}
        assert custom.get("artifact_hash") == sha

    def test_resume_ignores_tampered_artifact(self, mock_substrate, workspace_root):
        wi, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={"spec_section": "Tamper test", "ac_ids": ["AC-01"]},
        )
        mock_substrate.register_actor_role("test-worker", "interface_architect")
        claim = mock_substrate.acquire_claim(wi.work_item_id, "test-worker")
        mock_substrate.transition(
            wi.work_item_id,
            "claim",
            "test-worker",
            actor_metadata={"role": "interface_architect"},
        )

        data = b"def foo() -> int: ..."
        sha = compute_sha256(data)
        manifest = ArtifactManifest(
            attempt_number=1,
            work_item_id=str(wi.work_item_id),
            artifact_name="artifact.pyi",
            artifact_sha256=sha,
            artifact_size=len(data),
            actor_id="factory-worker-test",
            channel="claude-code",
            family="anthropic",
            context_hash="ctx-hash-2",
        )
        ad = attempt_dir(workspace_root, str(wi.work_item_id), 1)
        write_artifact(ad, "artifact.pyi", data, manifest)
        (ad / "artifact.pyi").write_bytes(b"tampered")

        invoked = False

        class _FreshChannel:
            @property
            def name(self) -> str:
                return "fresh"

            @property
            def family(self) -> str:
                return "test"

            def invoke(self, role, prompt, inputs_dir, outputs_dir, timeout):
                nonlocal invoked
                invoked = True
                outputs_dir.mkdir(parents=True, exist_ok=True)
                fresh = b"def bar() -> str: ..."
                (outputs_dir / "artifact.pyi").write_bytes(fresh)
                return InvocationResult(success=True, artifact_name="artifact.pyi")

        config = FactoryConfig(workspace_root=workspace_root)
        runtime = PipelineRuntime(
            sub=mock_substrate, config=config, spec_content="Tamper test", channel=_FreshChannel()
        )
        process_work_item(
            runtime,
            wi,
            "test-worker",
            claim,
            "interface_architect",
        )

        assert invoked
        updated = mock_substrate.get_work_item(wi.work_item_id)
        assert updated.current_state == "gating"
