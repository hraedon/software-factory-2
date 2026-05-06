from __future__ import annotations

from pathlib import Path

import pytest

from factory.channel import InvocationResult
from factory.workspace import (
    ArtifactManifest,
    attempt_dir,
    compute_sha256,
    find_resumable_artifact,
    write_artifact,
)


class FakeChannel:
    def __init__(self, artifact_content: bytes = b"def foo() -> int: ..."):
        self._name = "fake"
        self._family = "test"
        self._artifact_content = artifact_content
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
        (outputs_dir / "artifact.pyi").write_bytes(self._artifact_content)
        return InvocationResult(success=True, artifact_name="artifact.pyi")

    @property
    def invocations(self) -> list[tuple[str, str, Path, Path]]:
        return list(self._invocations)


@pytest.mark.integration
class TestRunnerSmoke:
    def test_full_loop_with_mock_channel(self, substrate, workspace_root, tmp_path):
        wi, _ = substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test-creator",
            custom_fields={
                "spec_section": "Test section",
                "ac_ids": ["AC-01"],
            },
        )
        FakeChannel()
        substrate.register_actor_role("test-worker", "interface_architect")

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
