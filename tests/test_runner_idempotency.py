from __future__ import annotations

from factory.workspace import (
    ArtifactManifest,
    attempt_dir,
    compute_sha256,
    find_resumable_artifact,
    quarantine_attempt,
    write_artifact,
)


def _make_manifest(
    attempt_number: int = 1,
    work_item_id: str = "wi-idem",
    **overrides,
) -> ArtifactManifest:
    defaults = {
        "attempt_number": attempt_number,
        "work_item_id": work_item_id,
        "artifact_name": "artifact.pyi",
        "artifact_sha256": "placeholder",
        "artifact_size": 0,
    }
    defaults.update(overrides)
    return ArtifactManifest(**defaults)


class TestCrashBeforeSubmit:
    def test_resume_from_prior_attempt(self, workspace_root):
        data = b"def foo() -> int: ..."
        sha = compute_sha256(data)
        manifest = _make_manifest(
            attempt_number=1,
            work_item_id="wi-crash1",
            artifact_sha256=sha,
            artifact_size=len(data),
            channel="claude-code",
            family="anthropic",
            context_hash="ctx-hash-1",
        )
        ad = attempt_dir(workspace_root, "wi-crash1", 1)
        write_artifact(ad, "artifact.pyi", data, manifest)
        result = find_resumable_artifact(workspace_root, "wi-crash1")
        assert result is not None
        num, found = result
        assert num == 1
        assert found.channel == "claude-code"
        assert found.family == "anthropic"
        assert found.context_hash == "ctx-hash-1"


class TestCrashDuringWrite:
    def test_partial_write_not_resumable(self, workspace_root):
        ad = attempt_dir(workspace_root, "wi-crash2", 1)
        ad.mkdir(parents=True, exist_ok=True)
        (ad / "artifact.pyi").write_bytes(b"partial content, no manifest")
        result = find_resumable_artifact(workspace_root, "wi-crash2")
        assert result is None

    def test_quarantine_partial_and_retry(self, workspace_root):
        ad = attempt_dir(workspace_root, "wi-crash2b", 1)
        ad.mkdir(parents=True, exist_ok=True)
        (ad / "artifact.pyi").write_bytes(b"no manifest")
        quarantine_attempt(ad)
        data = b"correct content"
        sha = compute_sha256(data)
        manifest = _make_manifest(
            attempt_number=2,
            work_item_id="wi-crash2b",
            artifact_sha256=sha,
            artifact_size=len(data),
        )
        ad2 = attempt_dir(workspace_root, "wi-crash2b", 2)
        write_artifact(ad2, "artifact.pyi", data, manifest)
        result = find_resumable_artifact(workspace_root, "wi-crash2b")
        assert result is not None
        num, found = result
        assert num == 2


class TestManifestTampering:
    def test_tampered_artifact_not_resumable(self, workspace_root):
        data = b"original content"
        sha = compute_sha256(data)
        manifest = _make_manifest(
            attempt_number=1,
            work_item_id="wi-tamper1",
            artifact_sha256=sha,
            artifact_size=len(data),
        )
        ad = attempt_dir(workspace_root, "wi-tamper1", 1)
        write_artifact(ad, "artifact.pyi", data, manifest)
        (ad / "artifact.pyi").write_bytes(b"tampered content")
        result = find_resumable_artifact(workspace_root, "wi-tamper1")
        assert result is None

    def test_quarantine_tampered(self, workspace_root):
        data = b"original content"
        sha = compute_sha256(data)
        manifest = _make_manifest(
            attempt_number=1,
            work_item_id="wi-tamper2",
            artifact_sha256=sha,
            artifact_size=len(data),
        )
        ad = attempt_dir(workspace_root, "wi-tamper2", 1)
        write_artifact(ad, "artifact.pyi", data, manifest)
        (ad / "artifact.pyi").write_bytes(b"tampered content")
        quarantine_attempt(ad)
        corrupt_dir = workspace_root / "wi-tamper2" / ".corrupt"
        assert corrupt_dir.exists()


class TestMultiCrash:
    def test_valid_first_corrupt_second(self, workspace_root):
        data1 = b"first valid"
        sha1 = compute_sha256(data1)
        m1 = _make_manifest(
            attempt_number=1,
            work_item_id="wi-multi1",
            artifact_sha256=sha1,
            artifact_size=len(data1),
        )
        ad1 = attempt_dir(workspace_root, "wi-multi1", 1)
        write_artifact(ad1, "artifact.pyi", data1, m1)
        ad2 = attempt_dir(workspace_root, "wi-multi1", 2)
        ad2.mkdir(parents=True, exist_ok=True)
        (ad2 / "artifact.pyi").write_bytes(b"partial, no manifest")
        result = find_resumable_artifact(workspace_root, "wi-multi1")
        assert result is not None
        num, found = result
        assert num == 1

    def test_both_valid_picks_highest(self, workspace_root):
        data1 = b"first valid"
        data2 = b"second valid"
        sha1 = compute_sha256(data1)
        sha2 = compute_sha256(data2)
        m1 = _make_manifest(
            attempt_number=1,
            work_item_id="wi-multi2",
            artifact_sha256=sha1,
            artifact_size=len(data1),
        )
        m2 = _make_manifest(
            attempt_number=2,
            work_item_id="wi-multi2",
            artifact_sha256=sha2,
            artifact_size=len(data2),
        )
        ad1 = attempt_dir(workspace_root, "wi-multi2", 1)
        ad2 = attempt_dir(workspace_root, "wi-multi2", 2)
        write_artifact(ad1, "artifact.pyi", data1, m1)
        write_artifact(ad2, "artifact.pyi", data2, m2)
        result = find_resumable_artifact(workspace_root, "wi-multi2")
        assert result is not None
        num, found = result
        assert num == 2
        assert found.artifact_sha256 == sha2

    def test_corrupt_first_valid_second(self, workspace_root):
        ad1 = attempt_dir(workspace_root, "wi-multi3", 1)
        ad1.mkdir(parents=True, exist_ok=True)
        (ad1 / "artifact.pyi").write_bytes(b"corrupt, no manifest")
        data2 = b"valid second"
        sha2 = compute_sha256(data2)
        m2 = _make_manifest(
            attempt_number=2,
            work_item_id="wi-multi3",
            artifact_sha256=sha2,
            artifact_size=len(data2),
        )
        ad2 = attempt_dir(workspace_root, "wi-multi3", 2)
        write_artifact(ad2, "artifact.pyi", data2, m2)
        result = find_resumable_artifact(workspace_root, "wi-multi3")
        assert result is not None
        num, found = result
        assert num == 2
