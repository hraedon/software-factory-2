from __future__ import annotations

import hashlib

from factory.spec_hash import (
    SpecHash,
    compare_spec_hashes,
    compute_spec_hash,
)


class TestComputeSpecHash:
    def test_hashes_spec_files(self, tmp_path):
        (tmp_path / "spec.md").write_text("# Test Spec\n## FR-01: Do thing")
        (tmp_path / "spec.yaml").write_text("name: test\nversion: 1\n")
        result = compute_spec_hash(tmp_path)
        assert result.hash_hex
        assert len(result.files) == 2
        assert "spec.md" in result.files
        assert "spec.yaml" in result.files

    def test_empty_dir(self, tmp_path):
        result = compute_spec_hash(tmp_path)
        assert len(result.files) == 0
        assert result.hash_hex == hashlib.sha256(b"").hexdigest()

    def test_nonexistent_dir(self, tmp_path):
        result = compute_spec_hash(tmp_path / "nonexistent")
        assert result.hash_hex == ""
        assert result.files == []

    def test_deterministic(self, tmp_path):
        (tmp_path / "spec.md").write_text("same content")
        h1 = compute_spec_hash(tmp_path)
        h2 = compute_spec_hash(tmp_path)
        assert h1.hash_hex == h2.hash_hex

    def test_changes_on_content_change(self, tmp_path):
        (tmp_path / "spec.md").write_text("version 1")
        h1 = compute_spec_hash(tmp_path)
        (tmp_path / "spec.md").write_text("version 2")
        h2 = compute_spec_hash(tmp_path)
        assert h1.hash_hex != h2.hash_hex

    def test_ignores_non_spec_files(self, tmp_path):
        (tmp_path / "spec.md").write_text("content")
        (tmp_path / "data.json").write_text("{}")
        result = compute_spec_hash(tmp_path)
        assert len(result.files) == 1
        assert "data.json" not in result.files


class TestCompareSpecHashes:
    def test_no_old_hash(self):
        new = SpecHash(hash_hex="abc123", files=["spec.md"], computed_at="2026-01-01")
        diff = compare_spec_hashes(None, new)
        assert diff.changed is True
        assert "new spec" in diff.summary.lower() or "No previous" in diff.summary

    def test_same_hash(self):
        new = SpecHash(hash_hex="abc123", files=["spec.md"], computed_at="2026-01-01")
        diff = compare_spec_hashes("abc123", new)
        assert diff.changed is False
        assert "unchanged" in diff.summary.lower()

    def test_different_hash(self):
        new = SpecHash(hash_hex="def456", files=["spec.md"], computed_at="2026-01-01")
        diff = compare_spec_hashes("abc123", new)
        assert diff.changed is True
        assert "changed" in diff.summary.lower()
