from __future__ import annotations

import pytest

from factory.channel import Channel, InvocationResult
from factory.workspace import ArtifactManifest, attempt_dir, compute_sha256, write_artifact
from tests._mock_channel import MockChannel


@pytest.fixture()
def fixtures_dir(tmp_path):
    d = tmp_path / "fixtures"
    d.mkdir()
    return d


class TestInvocationResult:
    def test_frozen(self):
        r = InvocationResult(success=True, artifact_name="a.pyi")
        with pytest.raises(AttributeError):
            r.success = False

    def test_defaults(self):
        r = InvocationResult(success=False)
        assert r.artifact_name is None
        assert r.error_message is None
        assert r.exit_code is None
        assert r.timed_out is False


class TestMockChannel:
    def test_protocol_conformance(self, fixtures_dir):
        ch = MockChannel(fixtures_dir)
        assert isinstance(ch, Channel)

    def test_invokes_with_artifact(self, fixtures_dir):
        role_dir = fixtures_dir / "interface_architect"
        role_dir.mkdir()
        (role_dir / "artifact.pyi").write_text("def foo() -> int: ...")
        outputs = fixtures_dir / "outputs"
        ch = MockChannel(fixtures_dir)
        result = ch.invoke("interface_architect", "prompt", outputs, 60)
        assert result.success
        assert result.artifact_name == "artifact.pyi"
        assert (outputs / "artifact.pyi").read_text() == "def foo() -> int: ..."

    def test_invokes_with_cannot_proceed(self, fixtures_dir):
        role_dir = fixtures_dir / "interface_architect"
        role_dir.mkdir()
        (role_dir / "cannot_proceed.json").write_text(
            '{"status": "cannot_proceed", "reason": "ambiguous"}'
        )
        outputs = fixtures_dir / "outputs"
        ch = MockChannel(fixtures_dir)
        result = ch.invoke("interface_architect", "prompt", outputs, 60)
        assert not result.success
        assert result.error_message == "cannot_proceed"

    def test_call_logging(self, fixtures_dir):
        role_dir = fixtures_dir / "interface_architect"
        role_dir.mkdir()
        (role_dir / "artifact.pyi").write_text("def foo() -> int: ...")
        outputs = fixtures_dir / "outputs"
        ch = MockChannel(fixtures_dir)
        ch.invoke("interface_architect", "prompt text", outputs, 60)
        assert len(ch.call_log) == 1
        assert ch.call_log[0][0] == "interface_architect"
        assert ch.call_log[0][1] == "prompt text"

    def test_round_trip_with_workspace(self, fixtures_dir, workspace_root):
        role_dir = fixtures_dir / "interface_architect"
        role_dir.mkdir()
        artifact_data = b"def foo() -> int: ..."
        (role_dir / "artifact.pyi").write_bytes(artifact_data)
        ch = MockChannel(fixtures_dir)
        ad = attempt_dir(workspace_root, "wi-abc", 1)
        result = ch.invoke("interface_architect", "prompt", ad, 60)
        assert result.success
        sha = compute_sha256(artifact_data)
        manifest = ArtifactManifest(
            attempt_number=1,
            work_item_id="wi-abc",
            artifact_name="artifact.pyi",
            artifact_sha256=sha,
            artifact_size=len(artifact_data),
            channel="mock",
        )
        write_artifact(ad, "artifact.pyi", artifact_data, manifest)
        read_back = (ad / "artifact.pyi").read_bytes()
        assert read_back == artifact_data
