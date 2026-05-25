from __future__ import annotations

from pathlib import Path

import pytest

from factory.dep_resolution import _safe_artifact_path
from factory.workspace import ArtifactManifest, attempt_dir, write_artifact


class TestSafeArtifactPath:
    def test_normal_relative_path(self):
        p = _safe_artifact_path("artifact.py")
        assert p is not None

    def test_normal_relative_path_with_dirs(self):
        p = _safe_artifact_path("some/dir/artifact.py")
        assert p is not None

    def test_normal_absolute_path_allowed(self):
        p = _safe_artifact_path("/tmp/ws/item-1/attempt-01/artifact.py")
        assert p is not None

    def test_absolute_path_escape_rejected(self):
        from factory.dep_resolution import _validate_readable_path

        assert not _validate_readable_path(Path("/etc/passwd"))
        assert not _validate_readable_path(Path("/home/user/.ssh/id_rsa"))

    def test_absolute_tmp_path_allowed(self):
        from factory.dep_resolution import _validate_readable_path

        assert _validate_readable_path(Path("/tmp/ws/item-1/artifact.py"))
        assert _validate_readable_path(Path("/var/tmp/ws/artifact.py"))

    def test_none_returns_none(self):
        assert _safe_artifact_path(None) is None

    def test_empty_string_returns_none(self):
        assert _safe_artifact_path("") is None

    def test_path_traversal_rejected(self):
        assert _safe_artifact_path("../../etc/passwd") is None

    def test_nested_traversal_rejected(self):
        assert _safe_artifact_path("subdir/../../../etc/shadow") is None

    def test_relative_traversal_rejected(self):
        assert _safe_artifact_path("subdir/../../etc/passwd") is None

    def test_absolute_path_with_dotdot_rejected(self):
        assert _safe_artifact_path("/tmp/../etc/passwd") is None


class TestWorkspacePathValidation:
    def test_work_item_id_with_slash_raises(self):
        with pytest.raises(ValueError, match="path traversal"):
            attempt_dir(Path("/tmp/ws"), "abc/def", 1)

    def test_work_item_id_with_dotdot_raises(self):
        with pytest.raises(ValueError, match="path traversal"):
            attempt_dir(Path("/tmp/ws"), "..etc", 1)

    def test_artifact_name_with_slash_raises(self):
        manifest = ArtifactManifest(
            attempt_number=1,
            work_item_id="test-wi",
            artifact_name="evil.py",
            artifact_sha256="abc",
            artifact_size=0,
        )
        with pytest.raises(ValueError, match="path traversal"):
            write_artifact(Path("/tmp/ws"), "../evil.py", b"data", manifest)

    def test_valid_work_item_id_passes(self):
        result = attempt_dir(Path("/tmp/ws"), "550e8400-e29b-41d4-a716-446655440000", 1)
        assert str(result).endswith("attempt-0001")
