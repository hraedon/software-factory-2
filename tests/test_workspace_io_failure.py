from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from factory.workspace import (
    attempt_dir,
    compute_sha256,
    quarantine_attempt,
    write_artifact,
)
from tests._helpers import make_manifest


class TestWriteArtifactIOFailure:
    def test_mkdir_failure_raises(self, workspace_root):
        ad = attempt_dir(workspace_root, "wi-io", 1)
        manifest = make_manifest(work_item_id="wi-io")
        with patch.object(Path, "mkdir", side_effect=PermissionError("read-only fs")):
            with pytest.raises(PermissionError, match="read-only fs"):
                write_artifact(ad, "artifact.pyi", b"data", manifest)

    def test_write_bytes_failure_raises(self, workspace_root):
        ad = attempt_dir(workspace_root, "wi-io", 1)
        manifest = make_manifest(work_item_id="wi-io")
        with patch.object(Path, "write_bytes", side_effect=OSError("disk full")):
            with pytest.raises(OSError, match="disk full"):
                write_artifact(ad, "artifact.pyi", b"data", manifest)


class TestComputeSHA256:
    def test_empty_bytes(self):
        assert (
            compute_sha256(b"")
            == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        )

    def test_known_hash(self):
        assert (
            compute_sha256(b"hello")
            == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
        )


class TestQuarantineAttemptIOFailure:
    def test_rename_failure_raises(self, workspace_root):
        ad = attempt_dir(workspace_root, "wi-io", 1)
        ad.mkdir(parents=True, exist_ok=True)
        (ad / "artifact.pyi").write_bytes(b"data")
        with patch("os.replace", side_effect=OSError("cross-device link")):
            with pytest.raises(OSError, match="cross-device link"):
                quarantine_attempt(ad)

