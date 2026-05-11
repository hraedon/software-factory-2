from __future__ import annotations

from factory.dep_resolution import _safe_artifact_path


class TestSafeArtifactPath:
    def test_normal_path(self):
        p = _safe_artifact_path("/tmp/ws/item-1/attempt-01/artifact.py")
        assert p is not None
        assert str(p).startswith("/tmp")

    def test_none_returns_none(self):
        assert _safe_artifact_path(None) is None

    def test_empty_string_returns_none(self):
        assert _safe_artifact_path("") is None

    def test_path_traversal_rejected(self):
        assert _safe_artifact_path("../../etc/passwd") is None

    def test_nested_traversal_rejected(self):
        assert _safe_artifact_path("/tmp/ws/../../../etc/shadow") is None

    def test_relative_traversal_rejected(self):
        assert _safe_artifact_path("subdir/../../etc/passwd") is None

    def test_normal_relative_path(self):
        p = _safe_artifact_path("artifact.py")
        assert p is not None

    def test_absolute_path_with_dotdot(self):
        assert _safe_artifact_path("/tmp/../etc/passwd") is None
