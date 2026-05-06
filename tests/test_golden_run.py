from __future__ import annotations

import json
from pathlib import Path

from factory.workspace import (
    ArtifactManifest,
    attempt_dir,
    compute_sha256,
    write_artifact,
)

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load_golden_run(fixture_name: str) -> dict | None:
    run_dir = FIXTURES_DIR / fixture_name
    metadata = run_dir / "metadata.json"
    if not metadata.exists():
        return None
    return json.loads(metadata.read_text())


def _golden_run_work_items(fixture_name: str) -> list[str]:
    run_dir = FIXTURES_DIR / fixture_name
    if not run_dir.exists():
        return []
    items = []
    for entry in sorted(run_dir.iterdir()):
        if entry.is_dir() and not entry.name.startswith(".") and entry.name.startswith("wi-"):
            items.append(entry.name)
    return items


class TestGoldenRunStructure:
    def test_fixture_dir_exists(self):
        assert FIXTURES_DIR.exists()

    def test_golden_run_001_placeholder_exists(self):
        run_dir = FIXTURES_DIR / "golden-run-001"
        assert run_dir.exists()

    def test_golden_run_manifest_round_trip(self, workspace_root):
        work_item_id = "wi-golden-test-001"
        data = b"from typing import Union\n\ndef foo(x: int) -> str: ...\n"
        sha = compute_sha256(data)
        manifest = ArtifactManifest(
            attempt_number=1,
            work_item_id=work_item_id,
            artifact_name="artifact.pyi",
            artifact_sha256=sha,
            artifact_size=len(data),
            actor_id="claude-code-worker",
            channel="claude-code",
            family="anthropic",
            context_hash="golden-ctx-hash-001",
        )
        ad = attempt_dir(workspace_root, work_item_id, 1)
        write_artifact(ad, "artifact.pyi", data, manifest)
        manifest_path = ad / "manifest.json"
        loaded = json.loads(manifest_path.read_text())
        assert loaded["artifact_sha256"] == sha
        assert loaded["channel"] == "claude-code"
        assert loaded["family"] == "anthropic"
        assert loaded["context_hash"] == "golden-ctx-hash-001"


class TestGoldenRunPending:
    def test_golden_run_001_not_yet_populated(self):
        result = _load_golden_run("golden-run-001")
        assert result is None or "work_items" not in result

    def test_golden_run_001_no_work_items_yet(self):
        items = _golden_run_work_items("golden-run-001")
        assert items == []
