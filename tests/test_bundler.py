from __future__ import annotations

import json
import tarfile
import zipfile
from pathlib import Path

import pytest

from factory.bundler import (
    BundleEntry,
    BundleManifest,
    create_bundle,
    verify_bundle_integrity,
)
from factory.workspace import ArtifactManifest, compute_sha256, write_artifact


def _make_workspace(ws: Path) -> None:
    wi1 = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    ad1 = ws / wi1 / "attempt-0001"
    ad1.mkdir(parents=True)
    artifact_data = b"def parse(): pass\n"
    manifest1 = ArtifactManifest(
        attempt_number=1,
        work_item_id=wi1,
        artifact_name="parser.py",
        artifact_sha256=compute_sha256(artifact_data),
        artifact_size=len(artifact_data),
    )
    write_artifact(ad1, "parser.py", artifact_data, manifest1)
    (ad1 / "parser.py.orig").write_bytes(b"old content")

    wi2 = "ffffffff-0000-1111-2222-333333333333"
    ad2 = ws / wi2 / "attempt-0001"
    ad2.mkdir(parents=True)
    test_data = b"def test_parse(): pass\n"
    manifest2 = ArtifactManifest(
        attempt_number=1,
        work_item_id=wi2,
        artifact_name="test_parser.py",
        artifact_sha256=compute_sha256(test_data),
        artifact_size=len(test_data),
    )
    write_artifact(ad2, "test_parser.py", test_data, manifest2)


class TestCreateBundleTarGz:
    def test_creates_tar_gz(self, tmp_path):
        ws = tmp_path / "workspace"
        _make_workspace(ws)
        output = tmp_path / "bundle.tar.gz"
        manifest = create_bundle(ws, "test-project", 5, output, output_format="tar.gz")
        assert output.exists()
        assert manifest.project_name == "test-project"
        assert manifest.bundle_version == "1"
        assert len(manifest.work_items) >= 1

    def test_tar_gz_contains_manifest(self, tmp_path):
        ws = tmp_path / "workspace"
        _make_workspace(ws)
        output = tmp_path / "bundle.tar.gz"
        create_bundle(ws, "test-project", 5, output)
        with tarfile.open(str(output), "r:gz") as tar:
            names = tar.getnames()
            assert any("MANIFEST.json" in n for n in names)

    def test_tar_gz_contains_src(self, tmp_path):
        ws = tmp_path / "workspace"
        _make_workspace(ws)
        output = tmp_path / "bundle.tar.gz"
        create_bundle(ws, "test-project", 5, output)
        with tarfile.open(str(output), "r:gz") as tar:
            names = tar.getnames()
            assert any("parser.py" in n for n in names)


class TestCreateBundleZip:
    def test_creates_zip(self, tmp_path):
        ws = tmp_path / "workspace"
        _make_workspace(ws)
        output = tmp_path / "bundle.zip"
        manifest = create_bundle(ws, "test-project", 5, output, output_format="zip")
        assert output.exists()
        assert manifest.project_name == "test-project"

    def test_zip_contains_manifest(self, tmp_path):
        ws = tmp_path / "workspace"
        _make_workspace(ws)
        output = tmp_path / "bundle.zip"
        create_bundle(ws, "test-project", 5, output, output_format="zip")
        with zipfile.ZipFile(str(output)) as zf:
            names = zf.namelist()
            assert any("MANIFEST.json" in n for n in names)


class TestCreateBundleDir:
    def test_creates_directory(self, tmp_path):
        ws = tmp_path / "workspace"
        _make_workspace(ws)
        output = tmp_path / "bundle-output"
        create_bundle(ws, "test-project", 5, output, output_format="dir")
        assert output.exists()
        assert (output / "MANIFEST.json").exists()

    def test_dir_contains_artifacts(self, tmp_path):
        ws = tmp_path / "workspace"
        _make_workspace(ws)
        output = tmp_path / "bundle-output"
        create_bundle(ws, "test-project", 5, output, output_format="dir")
        manifest = json.loads((output / "MANIFEST.json").read_text())
        assert len(manifest["work_items"]) >= 1


class TestVerifyBundleIntegrity:
    def test_valid_dir_bundle(self, tmp_path):
        ws = tmp_path / "workspace"
        _make_workspace(ws)
        output = tmp_path / "bundle-output"
        create_bundle(ws, "test-project", 5, output, output_format="dir")
        result = verify_bundle_integrity(output)
        assert result.passed
        assert result.entry_count >= 1

    def test_missing_path(self, tmp_path):
        result = verify_bundle_integrity(tmp_path / "nonexistent")
        assert not result.passed

    def test_missing_manifest(self, tmp_path):
        bundle = tmp_path / "bundle"
        bundle.mkdir()
        result = verify_bundle_integrity(bundle)
        assert not result.passed
        assert "MANIFEST.json" in result.diagnostics[0]

    def test_invalid_manifest(self, tmp_path):
        bundle = tmp_path / "bundle"
        bundle.mkdir()
        (bundle / "MANIFEST.json").write_text("not json")
        result = verify_bundle_integrity(bundle)
        assert not result.passed
        assert "Invalid" in result.diagnostics[0]


class TestBundleManifest:
    def test_to_dict(self):
        entry = BundleEntry(
            work_item_id="wi_001",
            item_type="implementation",
            module_name="parser",
            attempt_number=1,
            locked_at="2026-01-01T00:00:00",
            artifact_sha256="abc123",
            src_path="src/parser.py",
        )
        manifest = BundleManifest(
            bundle_version="1",
            project_name="test",
            workflow_version=5,
            created_at="2026-01-01T00:00:00",
            work_items=[entry],
        )
        d = manifest.to_dict()
        assert d["bundle_version"] == "1"
        assert len(d["work_items"]) == 1
        assert d["work_items"][0]["module_name"] == "parser"

    def test_unsupported_format(self, tmp_path):
        ws = tmp_path / "workspace"
        ws.mkdir()
        output = tmp_path / "bundle.rar"
        with pytest.raises(ValueError, match="Unsupported"):
            create_bundle(ws, "test", 5, output, output_format="rar")
