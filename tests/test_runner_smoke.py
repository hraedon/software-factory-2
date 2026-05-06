from __future__ import annotations

from pathlib import Path

import pytest

from factory.channel import InvocationResult
from factory.config import FactoryConfig
from factory.gate_process import process_gate_item
from factory.runner import process_work_item
from factory.workspace import (
    ArtifactManifest,
    attempt_dir,
    compute_sha256,
    find_resumable_artifact,
    write_artifact,
)


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
        inputs_dir: Path,
        outputs_dir: Path,
        timeout: int,
    ) -> InvocationResult:
        self._invocations.append((role, prompt, inputs_dir, outputs_dir))
        outputs_dir.mkdir(parents=True, exist_ok=True)
        ac_doc = ", ".join(self._ac_ids) if self._ac_ids else "AC-placeholder"
        content = f'"""Satisfies {ac_doc}."""\ndef foo() -> int: ...\n'
        (outputs_dir / "artifact.pyi").write_text(content)
        return InvocationResult(success=True, artifact_name="artifact.pyi")

    @property
    def invocations(self) -> list[tuple[str, str, Path, Path]]:
        return list(self._invocations)


@pytest.mark.integration
class TestRunnerSmoke:
    def test_full_loop_with_mock_channel(self, substrate, workspace_root, tmp_path):
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
        config = FactoryConfig(
            dsn=substrate._mgr._dsn,
            project_name=substrate._project,
            hmac_key_path="tests/test_keys.json",
            workspace_root=workspace_root,
        )
        fake_channel = FakeChannel(ac_ids=["AC-01"])
        process_work_item(
            substrate,
            config,
            fake_channel,
            wi,
            "test-worker",
            claim,
            "interface_architect",
            spec_content="Test section",
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
        process_gate_item(substrate, config, fresh, "test-gate", gate_claim)

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
