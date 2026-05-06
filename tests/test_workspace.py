from __future__ import annotations

import json
from pathlib import Path

from factory.workspace import (
    ArtifactManifest,
    attempt_dir,
    compute_sha256,
    find_resumable_artifact,
    list_attempt_dirs,
    quarantine_attempt,
    write_artifact,
)


def _make_manifest(
    attempt_number: int = 1,
    artifact_name: str = "artifact.pyi",
    **overrides,
) -> ArtifactManifest:
    defaults = {
        "attempt_number": attempt_number,
        "work_item_id": "wi-test",
        "artifact_name": artifact_name,
        "artifact_sha256": "sha256placeholder",
        "artifact_size": 0,
    }
    defaults.update(overrides)
    return ArtifactManifest(**defaults)


class TestAttemptDir:
    def test_formats_attempt_number_with_zero_padding(self):
        result = attempt_dir(Path("/root"), "wi-abc", 1)
        assert result == Path("/root/wi-abc/attempt-0001")

    def test_high_attempt_number(self):
        result = attempt_dir(Path("/root"), "wi-abc", 42)
        assert result == Path("/root/wi-abc/attempt-0042")


class TestWriteArtifact:
    def test_round_trip(self, workspace_root):
        ad = attempt_dir(workspace_root, "wi-1", 1)
        data = b"class Foo: ..."
        sha = compute_sha256(data)
        manifest = _make_manifest(
            attempt_number=1,
            work_item_id="wi-1",
            artifact_name="artifact.pyi",
            artifact_sha256=sha,
            artifact_size=len(data),
        )
        path = write_artifact(ad, "artifact.pyi", data, manifest)
        assert path.exists()
        assert path.read_bytes() == data
        manifest_path = ad / "manifest.json"
        assert manifest_path.exists()
        loaded = json.loads(manifest_path.read_text())
        assert loaded["artifact_sha256"] == sha
        assert loaded["artifact_size"] == len(data)

    def test_overwrite_does_not_corrupt(self, workspace_root):
        ad = attempt_dir(workspace_root, "wi-1", 1)
        data1 = b"version one"
        data2 = b"version two"
        sha1 = compute_sha256(data1)
        m1 = _make_manifest(
            attempt_number=1,
            work_item_id="wi-1",
            artifact_sha256=sha1,
            artifact_size=len(data1),
        )
        write_artifact(ad, "artifact.pyi", data1, m1)
        sha2 = compute_sha256(data2)
        m2 = _make_manifest(
            attempt_number=1,
            work_item_id="wi-1",
            artifact_sha256=sha2,
            artifact_size=len(data2),
        )
        write_artifact(ad, "artifact.pyi", data2, m2)
        assert (ad / "artifact.pyi").read_bytes() == data2
        loaded = json.loads((ad / "manifest.json").read_text())
        assert loaded["artifact_sha256"] == sha2


class TestFindResumableArtifact:
    def test_no_attempts_returns_none(self, workspace_root):
        result = find_resumable_artifact(workspace_root, "wi-none")
        assert result is None

    def test_single_valid_attempt(self, workspace_root):
        data = b"valid content"
        sha = compute_sha256(data)
        manifest = _make_manifest(
            attempt_number=1,
            work_item_id="wi-1",
            artifact_sha256=sha,
            artifact_size=len(data),
        )
        ad = attempt_dir(workspace_root, "wi-1", 1)
        write_artifact(ad, "artifact.pyi", data, manifest)
        result = find_resumable_artifact(workspace_root, "wi-1")
        assert result is not None
        num, found_manifest = result
        assert num == 1
        assert found_manifest.artifact_sha256 == sha

    def test_multiple_attempts_highest_valid_wins(self, workspace_root):
        data1 = b"first attempt"
        data2 = b"second attempt"
        sha1 = compute_sha256(data1)
        sha2 = compute_sha256(data2)
        m1 = _make_manifest(
            attempt_number=1,
            work_item_id="wi-2",
            artifact_sha256=sha1,
            artifact_size=len(data1),
        )
        m2 = _make_manifest(
            attempt_number=2,
            work_item_id="wi-2",
            artifact_sha256=sha2,
            artifact_size=len(data2),
        )
        ad1 = attempt_dir(workspace_root, "wi-2", 1)
        ad2 = attempt_dir(workspace_root, "wi-2", 2)
        write_artifact(ad1, "artifact.pyi", data1, m1)
        write_artifact(ad2, "artifact.pyi", data2, m2)
        result = find_resumable_artifact(workspace_root, "wi-2")
        assert result is not None
        num, found_manifest = result
        assert num == 2
        assert found_manifest.artifact_sha256 == sha2

    def test_tampered_artifact_detected(self, workspace_root):
        data = b"original content"
        sha = compute_sha256(data)
        manifest = _make_manifest(
            attempt_number=1,
            work_item_id="wi-3",
            artifact_sha256=sha,
            artifact_size=len(data),
        )
        ad = attempt_dir(workspace_root, "wi-3", 1)
        write_artifact(ad, "artifact.pyi", data, manifest)
        (ad / "artifact.pyi").write_bytes(b"tampered content")
        result = find_resumable_artifact(workspace_root, "wi-3")
        assert result is None

    def test_missing_manifest(self, workspace_root):
        ad = attempt_dir(workspace_root, "wi-4", 1)
        ad.mkdir(parents=True, exist_ok=True)
        (ad / "artifact.pyi").write_bytes(b"orphaned content")
        result = find_resumable_artifact(workspace_root, "wi-4")
        assert result is None

    def test_valid_amidst_invalid(self, workspace_root):
        data_valid = b"valid attempt"
        sha_valid = compute_sha256(data_valid)
        m_valid = _make_manifest(
            attempt_number=1,
            work_item_id="wi-5",
            artifact_sha256=sha_valid,
            artifact_size=len(data_valid),
        )
        ad1 = attempt_dir(workspace_root, "wi-5", 1)
        write_artifact(ad1, "artifact.pyi", data_valid, m_valid)
        ad2 = attempt_dir(workspace_root, "wi-5", 2)
        ad2.mkdir(parents=True, exist_ok=True)
        (ad2 / "artifact.pyi").write_bytes(b"partial, no manifest")
        result = find_resumable_artifact(workspace_root, "wi-5")
        assert result is not None
        num, _ = result
        assert num == 1


class TestQuarantineAttempt:
    def test_quarantine_renames_directory(self, workspace_root):
        ad = attempt_dir(workspace_root, "wi-6", 1)
        ad.mkdir(parents=True, exist_ok=True)
        (ad / "artifact.pyi").write_bytes(b"data")
        dest = quarantine_attempt(ad)
        assert not ad.exists()
        assert dest.exists()
        assert dest.name.startswith("attempt-0001-")
        assert CORRUPT_DIR_NAME in str(dest)

    def test_quarantine_preserves_content(self, workspace_root):
        ad = attempt_dir(workspace_root, "wi-7", 1)
        ad.mkdir(parents=True, exist_ok=True)
        (ad / "artifact.pyi").write_bytes(b"preserved")
        dest = quarantine_attempt(ad)
        assert (dest / "artifact.pyi").read_bytes() == b"preserved"


CORRUPT_DIR_NAME = ".corrupt"


class TestListAttemptDirs:
    def test_empty_work_item(self, workspace_root):
        result = list_attempt_dirs(workspace_root, "wi-none")
        assert result == []

    def test_lists_attempt_dirs(self, workspace_root):
        ad1 = attempt_dir(workspace_root, "wi-8", 1)
        ad2 = attempt_dir(workspace_root, "wi-8", 2)
        ad1.mkdir(parents=True, exist_ok=True)
        ad2.mkdir(parents=True, exist_ok=True)
        result = list_attempt_dirs(workspace_root, "wi-8")
        assert len(result) == 2
        assert all(p.is_dir() for p in result)

    def test_ignores_corrupt_dir(self, workspace_root):
        ad = attempt_dir(workspace_root, "wi-9", 1)
        ad.mkdir(parents=True, exist_ok=True)
        corrupt = workspace_root / "wi-9" / CORRUPT_DIR_NAME
        corrupt.mkdir(parents=True, exist_ok=True)
        result = list_attempt_dirs(workspace_root, "wi-9")
        assert len(result) == 1
        assert result[0].name == "attempt-0001"
