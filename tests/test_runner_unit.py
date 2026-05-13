from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from factory.channel import InvocationResult
from factory.config import FactoryConfig, RoleConfig
from factory.context import PromptContext
from factory.runner import _process_jury_work_item, process_work_item
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

    def invoke(self, role, prompt, outputs_dir, timeout, extra_env=None):
        self._invocations.append((role, prompt, outputs_dir))
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

            def invoke(self, role, prompt, outputs_dir, timeout, extra_env=None):
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

            def invoke(self, role, prompt, outputs_dir, timeout, extra_env=None):
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


class TestProcessJuryWorkItemExceptionHandling:
    def test_jury_exception_records_channel_fail(self, mock_substrate, workspace_root):
        from factory.constants import ROLE_FRONTIER_JUDGE

        phase4_path = str(Path(__file__).parent.parent / "workflows" / "phase4.yaml")
        mock_substrate.register_workflow_file(phase4_path)

        iface, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={"spec_section": "Jury crash test", "ac_ids": ["AC-01"]},
        )
        ts, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="test_suite",
            actor_id="test-creator",
            custom_fields={
                "spec_section": "Test section",
                "ac_ids": ["AC-01"],
                "interface_ref": str(iface.work_item_id),
            },
        )
        impl, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="implementation",
            actor_id="test-creator",
            custom_fields={
                "spec_section": "Impl section",
                "ac_ids": ["AC-01"],
                "interface_ref": str(iface.work_item_id),
                "test_suite_ref": str(ts.work_item_id),
            },
        )
        review_wi, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="review",
            actor_id="test-creator",
            custom_fields={
                "spec_section": "Review section",
                "ac_ids": ["AC-01"],
                "interface_ref": str(iface.work_item_id),
                "test_suite_ref": str(ts.work_item_id),
                "implementation_ref": str(impl.work_item_id),
            },
        )
        wi, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="jury",
            actor_id="test-creator",
            custom_fields={
                "review_ref": str(review_wi.work_item_id),
            },
        )
        mock_substrate.register_actor_role("test-worker", "frontier_judge")
        claim = mock_substrate.acquire_claim(wi.work_item_id, "test-worker")
        mock_substrate.transition(
            wi.work_item_id,
            "claim",
            "test-worker",
            actor_metadata={"role": "frontier_judge"},
        )

        config = FactoryConfig(
            workspace_root=workspace_root,
            roles=(RoleConfig(role=ROLE_FRONTIER_JUDGE, channel="dummy"),),
        )
        runtime = PipelineRuntime(
            sub=mock_substrate,
            config=config,
            spec_content="Jury crash test",
            channels={"dummy": _FailingChannel(InvocationResult(success=True, artifact_name="x"))},
        )
        ctx = PromptContext(
            work_item_id=str(wi.work_item_id),
            role="frontier_judge",
            spec_section="Jury crash test",
            ac_ids=["AC-01"],
            glossary={},
            prior_failures=[],
            prompt_template="test prompt",
            context_hash="abc",
            prompt_template_hash="def",
            extra_artifacts={},
            stub_only_deps=[],
        )
        ad = attempt_dir(workspace_root, str(wi.work_item_id), 1)
        ad.mkdir(parents=True, exist_ok=True)

        with patch(
            "factory.jury.run_jury",
            side_effect=RuntimeError("jury infrastructure failure"),
        ):
            _process_jury_work_item(
                runtime,
                wi,
                "test-worker",
                claim,
                ctx,
                ad,
                60,
                None,
            )

        all_events = mock_substrate.read_events(work_item_id=wi.work_item_id)
        channel_fail_events = events_by_transition(all_events, "channel_fail")
        assert len(channel_fail_events) == 1
        payload = channel_fail_events[0].payload or {}
        diagnostics = payload.get("diagnostics", {})
        assert "exception" in diagnostics.get("error_message", "").lower()
