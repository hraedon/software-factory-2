from __future__ import annotations

from pathlib import Path

import pytest

from factory.channel import InvocationResult
from factory.config import FactoryConfig
from factory.gate_process import process_gate_item
from factory.runner import process_work_item
from factory.runtime import PipelineRuntime
from factory.workspace import (
    ArtifactManifest,
    attempt_dir,
    compute_sha256,
    find_resumable_artifact,
    write_artifact,
)
from tests._helpers import events_by_transition


class FakeChannel:
    def __init__(self, ac_ids: list[str] | None = None):
        self._name = "fake"
        self._family = "test"
        self._ac_ids = ac_ids or []
        self._invocations: list[tuple[str, str, Path, Path]] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def family(self) -> str:
        return self._family

    def invoke(
        self,
        role: str,
        prompt: str,
        outputs_dir: Path,
        timeout: int,
    ) -> InvocationResult:
        self._invocations.append((role, prompt, outputs_dir))
        outputs_dir.mkdir(parents=True, exist_ok=True)
        ac_doc = ", ".join(self._ac_ids) if self._ac_ids else "AC-01"
        content = f'def foo(x: int) -> str:\n    """Satisfies {ac_doc}."""\n    ...\n'
        (outputs_dir / "artifact.pyi").write_text(content)
        return InvocationResult(success=True, artifact_name="artifact.pyi")

    @property
    def invocations(self) -> list[tuple[str, str, Path, Path]]:
        return list(self._invocations)


@pytest.mark.integration
class TestRunnerSmoke:
    def test_full_loop_with_mock_channel(self, substrate, workspace_root, tmp_path, factory_config):
        # 1. Create work-item in 'new' state
        wi, _ = substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={
                "spec_section": "Test section",
                "ac_ids": ["AC-01"],
            },
        )
        substrate.register_actor_role("test-worker", "interface_architect")

        # 2. Acquire claim and move to 'in_progress'
        claim = substrate.acquire_claim(wi.work_item_id, "test-worker", ttl_seconds=300)
        substrate.transition(
            wi.work_item_id,
            "claim",
            "test-worker",
            actor_metadata={"role": "interface_architect"},
        )

        # 3. Run worker process step
        fake_channel = FakeChannel(ac_ids=["AC-01"])
        runtime = PipelineRuntime(
            sub=substrate, config=factory_config, spec_content="Test section", channel=fake_channel
        )
        process_work_item(
            runtime,
            wi,
            "test-worker",
            claim,
            "interface_architect",
        )

        # 4. Verify item is in 'gating'
        updated = substrate.get_work_item(wi.work_item_id)
        assert updated.current_state == "gating"

        # 5. Verify artifact written
        assert len(fake_channel.invocations) == 1
        invocation = fake_channel.invocations[0]
        assert invocation[0] == "interface_architect"
        assert "Test section" in invocation[1]  # prompt must contain spec_section
        assert "AC-01" in invocation[1]  # prompt must contain AC ID

        ad = attempt_dir(workspace_root, str(wi.work_item_id), 1)
        assert ad.exists()
        assert (ad / "artifact.pyi").exists()
        assert (ad / "manifest.json").exists()

        # 6. Run gate process step (use fresh work-item state)
        substrate.register_actor_role("test-gate", "mechanical_gate")
        gate_claim = substrate.acquire_claim(wi.work_item_id, "test-gate", ttl_seconds=300)
        fresh = substrate.get_work_item(wi.work_item_id)
        gate_runtime = PipelineRuntime(sub=substrate, config=factory_config)
        process_gate_item(gate_runtime, fresh, "test-gate", gate_claim)

        # 7. Verify item is in 'locked'
        final = substrate.get_work_item(wi.work_item_id)
        assert final.current_state == "locked"

    def test_workspace_artifacts_written(self, workspace_root, tmp_path):
        work_item_id = "wi-smoke-test"
        data = b"def parse_range(input: str) -> Result: ..."
        sha = compute_sha256(data)
        manifest = ArtifactManifest(
            attempt_number=1,
            work_item_id=work_item_id,
            artifact_name="artifact.pyi",
            artifact_sha256=sha,
            artifact_size=len(data),
            channel="fake",
            family="test",
            context_hash="abc123",
        )
        ad = attempt_dir(workspace_root, work_item_id, 1)
        write_artifact(ad, "artifact.pyi", data, manifest)
        found = find_resumable_artifact(workspace_root, work_item_id)
        assert found is not None
        num, found_manifest = found
        assert num == 1
        assert found_manifest.artifact_sha256 == sha

    def test_prompt_rendering_includes_spec_and_acs(self, substrate, workspace_root):
        """Ensure the rendered prompt contains spec_section text and AC IDs."""
        from factory.context import derive_context, render_prompt

        wi, _ = substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={
                "spec_section": "Parse a date range given a today anchor.",
                "ac_ids": ["AC-01", "AC-02"],
            },
        )
        ctx = derive_context(substrate, wi.work_item_id, "interface_architect")
        prompt = render_prompt(ctx)

        assert "Parse a date range given a today anchor." in prompt
        assert "AC-01" in prompt
        assert "AC-02" in prompt
        assert "interface_architect" in prompt
        assert "# Role: interface_architect" in prompt
        assert ctx.context_hash is not None


class TestWorkerLoopClaimTransition:
    def test_claim_event_recorded_in_mock_substrate(self, mock_substrate, workspace_root):
        wi, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={
                "spec_section": "Test spec for claim transition.",
                "ac_ids": ["AC-01"],
            },
        )
        config = FactoryConfig(
            workspace_root=workspace_root,
            poll_interval_seconds=0,
            claim_ttl_seconds=60,
        )
        fake_channel = FakeChannel(ac_ids=["AC-01"])
        mock_substrate.register_actor_role("factory-worker-fake", "interface_architect")

        def _run_loop_once():
            for role_name in config.worker_roles:
                try:
                    mock_substrate.register_actor_role("factory-worker-fake", role_name)
                except Exception:
                    pass
            page = mock_substrate.query_work_items(
                workflow_name=config.workflow_name,
                current_states=["new"],
                claimable_now=True,
                page_size=10,
            )
            for item in page.items:
                claim = mock_substrate.acquire_claim(
                    item.work_item_id, "factory-worker-fake", config.claim_ttl_seconds
                )
                mock_substrate.transition(
                    item.work_item_id,
                    "claim",
                    "factory-worker-fake",
                    actor_metadata={
                        "role": "interface_architect",
                        "channel": "fake",
                        "family": "test",
                    },
                )
                process_work_item(
                    PipelineRuntime(
                        sub=mock_substrate,
                        config=config,
                        spec_content="Test spec for claim transition.",
                        channel=fake_channel,
                    ),
                    item,
                    "factory-worker-fake",
                    claim,
                    "interface_architect",
                )
                break

        _run_loop_once()

        all_events = mock_substrate.read_events(work_item_id=wi.work_item_id)
        events = events_by_transition(all_events, "claim")
        assert len(events) == 1
        assert events[0].transition == "claim"

        updated = mock_substrate.get_work_item(wi.work_item_id)
        assert updated.current_state == "gating"

    def test_worker_loop_sets_in_progress_state(self, mock_substrate, workspace_root):
        wi, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={
                "spec_section": "Another test spec.",
                "ac_ids": ["AC-02"],
            },
        )
        config = FactoryConfig(
            workspace_root=workspace_root,
            poll_interval_seconds=0,
            claim_ttl_seconds=60,
        )
        fake_channel = FakeChannel(ac_ids=["AC-02"])
        mock_substrate.register_actor_role("factory-worker-fake", "interface_architect")

        claim = mock_substrate.acquire_claim(
            wi.work_item_id, "factory-worker-fake", config.claim_ttl_seconds
        )
        mock_substrate.transition(
            wi.work_item_id,
            "claim",
            "factory-worker-fake",
            actor_metadata={
                "role": "interface_architect",
                "channel": "fake",
                "family": "test",
            },
        )

        in_progress = mock_substrate.get_work_item(wi.work_item_id)
        assert in_progress.current_state == "in_progress"

        process_work_item(
            PipelineRuntime(
                sub=mock_substrate,
                config=config,
                spec_content="Another test spec.",
                channel=fake_channel,
            ),
            in_progress,
            "factory-worker-fake",
            claim,
            "interface_architect",
        )

        submitted = mock_substrate.get_work_item(wi.work_item_id)
        assert submitted.current_state == "gating"


@pytest.mark.integration
class TestWorkerLoopClaimTransitionLive:
    def test_claim_transition_on_live_substrate(self, substrate, workspace_root):
        wi, _ = substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={
                "spec_section": "Live claim transition test.",
                "ac_ids": ["AC-01"],
            },
        )
        substrate.register_actor_role("test-worker-claim", "interface_architect")
        substrate.acquire_claim(wi.work_item_id, "test-worker-claim", ttl_seconds=300)
        substrate.transition(
            wi.work_item_id,
            "claim",
            "test-worker-claim",
            actor_metadata={"role": "interface_architect"},
        )

        updated = substrate.get_work_item(wi.work_item_id)
        assert updated.current_state == "in_progress"

        all_events = substrate.read_events(work_item_id=wi.work_item_id)
        events = events_by_transition(all_events, "claim")
        assert len(events) >= 1
        assert events[-1].transition == "claim"
