from __future__ import annotations

import json
from unittest.mock import MagicMock

from factory.checkpoint import (
    PipelineCheckpoint,
    StageCheckpoint,
    _compute_config_hash,
    can_resume_from_checkpoint,
    compare_checkpoints,
    list_checkpoints,
    load_checkpoint,
    load_latest_checkpoint,
    write_checkpoint,
)
from factory.config import FactoryConfig


def _make_config(**overrides):
    defaults = {
        "workflow_name": "test-workflow",
        "workflow_version": 2,
        "project_name": "test-project",
        "workspace_root": "/tmp/test-ws",
        "query_page_size": 200,
    }
    defaults.update(overrides)
    return FactoryConfig(**defaults)


def _make_sub(items=None):
    sub = MagicMock()
    page = MagicMock()
    page.items = items or []
    sub.query_work_items.return_value = page
    return sub


def _make_wi(wi_id="w1", wi_type="implementation", state="locked", custom_fields=None):
    wi = MagicMock()
    wi.work_item_id = wi_id
    wi.work_item_type = wi_type
    wi.current_state = state
    wi.custom_fields = custom_fields or {}
    return wi


class TestWriteCheckpoint:
    def test_writes_json_file(self, tmp_path):
        sub = _make_sub(items=[])
        config = _make_config()
        cp = write_checkpoint(sub, config, checkpoint_dir=tmp_path)
        files = list(tmp_path.glob("checkpoint-*.json"))
        assert len(files) == 1
        assert cp.project_name == "test-project"

    def test_creates_latest_symlink(self, tmp_path):
        sub = _make_sub(items=[])
        config = _make_config()
        write_checkpoint(sub, config, checkpoint_dir=tmp_path)
        latest = tmp_path / "latest.json"
        assert latest.exists()
        data = json.loads(latest.read_text())
        assert data["project_name"] == "test-project"

    def test_captures_stage_data(self, tmp_path):
        items = [
            _make_wi("w1", "interface_spec", "locked"),
            _make_wi("w2", "implementation", "new"),
        ]
        sub = _make_sub(items=items)
        config = _make_config()
        cp = write_checkpoint(sub, config, checkpoint_dir=tmp_path)
        assert len(cp.stages) == 3
        spec_stage = cp.stages[0]
        assert spec_stage.stage_type == "interface_spec"
        assert spec_stage.total == 1
        assert spec_stage.by_state.get("locked") == 1

    def test_captures_artifact_paths(self, tmp_path):
        items = [
            _make_wi(
                "w1",
                "implementation",
                "locked",
                custom_fields={"artifact_path": "/tmp/test.py", "artifact_hash": "abc123"},
            ),
        ]
        sub = _make_sub(items=items)
        config = _make_config()
        cp = write_checkpoint(sub, config, checkpoint_dir=tmp_path)
        impl_stage = cp.stages[2]
        assert "w1" in impl_stage.artifact_paths
        assert impl_stage.artifact_paths["w1"] == "/tmp/test.py"


class TestLoadCheckpoint:
    def test_load_latest(self, tmp_path):
        sub = _make_sub(items=[])
        config = _make_config()
        write_checkpoint(sub, config, checkpoint_dir=tmp_path)
        loaded = load_latest_checkpoint(tmp_path)
        assert loaded is not None
        assert loaded.project_name == "test-project"

    def test_load_none_when_missing(self, tmp_path):
        loaded = load_latest_checkpoint(tmp_path / "nonexistent")
        assert loaded is None

    def test_load_specific_file(self, tmp_path):
        sub = _make_sub(items=[])
        config = _make_config()
        write_checkpoint(sub, config, checkpoint_dir=tmp_path)
        files = list(tmp_path.glob("checkpoint-*.json"))
        loaded = load_checkpoint(files[0])
        assert loaded.project_name == "test-project"


class TestCompareCheckpoints:
    def test_detects_progress(self):
        old = PipelineCheckpoint(
            checkpoint_version=1,
            project_name="test",
            workflow_name="phase2",
            workflow_version=2,
            config_hash="abc",
            created_at="2026-01-01",
            stages=[
                StageCheckpoint(
                    stage_type="interface_spec",
                    total=5,
                    by_state={"locked": 3, "new": 2},
                    locked_ids=["w1", "w2", "w3"],
                    failed_ids=[],
                    artifact_paths={},
                    artifact_hashes={},
                    timestamp="2026-01-01",
                ),
            ],
            summary={"locked": 3, "new": 2},
        )
        new = PipelineCheckpoint(
            checkpoint_version=1,
            project_name="test",
            workflow_name="phase2",
            workflow_version=2,
            config_hash="abc",
            created_at="2026-01-02",
            stages=[
                StageCheckpoint(
                    stage_type="interface_spec",
                    total=5,
                    by_state={"locked": 5},
                    locked_ids=["w1", "w2", "w3", "w4", "w5"],
                    failed_ids=[],
                    artifact_paths={},
                    artifact_hashes={},
                    timestamp="2026-01-02",
                ),
            ],
            summary={"locked": 5},
        )
        diff = compare_checkpoints(old, new)
        assert diff["config_changed"] is False
        assert diff["stages"][0]["locked_delta"] == 2

    def test_detects_config_change(self):
        old = PipelineCheckpoint(
            checkpoint_version=1,
            project_name="test",
            workflow_name="phase2",
            workflow_version=2,
            config_hash="old",
            created_at="2026-01-01",
            stages=[],
            summary={},
        )
        new = PipelineCheckpoint(
            checkpoint_version=1,
            project_name="test",
            workflow_name="phase2",
            workflow_version=2,
            config_hash="new",
            created_at="2026-01-02",
            stages=[],
            summary={},
        )
        diff = compare_checkpoints(old, new)
        assert diff["config_changed"] is True


class TestCanResumeFromCheckpoint:
    def test_same_config_resumable(self):
        config = _make_config()
        hash_val = _compute_config_hash(config)
        cp = PipelineCheckpoint(
            checkpoint_version=1,
            project_name="test-project",
            workflow_name="test-workflow",
            workflow_version=2,
            config_hash=hash_val,
            created_at="2026-01-01",
            stages=[],
            summary={},
        )
        ok, _msg = can_resume_from_checkpoint(cp, config)
        assert ok is True

    def test_different_project_not_resumable(self):
        config = _make_config()
        hash_val = _compute_config_hash(config)
        cp = PipelineCheckpoint(
            checkpoint_version=1,
            project_name="other-project",
            workflow_name="test-workflow",
            workflow_version=2,
            config_hash=hash_val,
            created_at="2026-01-01",
            stages=[],
            summary={},
        )
        ok, msg = can_resume_from_checkpoint(cp, config)
        assert ok is False
        assert "mismatch" in msg.lower()

    def test_config_changed_not_resumable(self):
        config = _make_config()
        cp = PipelineCheckpoint(
            checkpoint_version=1,
            project_name="test-project",
            workflow_name="test-workflow",
            workflow_version=2,
            config_hash="stale_hash",
            created_at="2026-01-01",
            stages=[],
            summary={},
        )
        ok, msg = can_resume_from_checkpoint(cp, config)
        assert ok is False
        assert "config" in msg.lower()


class TestListCheckpoints:
    def test_lists_sorted_checkpoints(self, tmp_path):
        sub = _make_sub(items=[])
        config = _make_config()
        write_checkpoint(sub, config, checkpoint_dir=tmp_path)
        write_checkpoint(sub, config, checkpoint_dir=tmp_path)
        cps = list_checkpoints(tmp_path)
        assert len(cps) == 2

    def test_empty_dir(self, tmp_path):
        cps = list_checkpoints(tmp_path)
        assert cps == []

    def test_nonexistent_dir(self, tmp_path):
        cps = list_checkpoints(tmp_path / "nonexistent")
        assert cps == []


class TestConfigHash:
    def test_same_config_same_hash(self):
        c1 = _make_config()
        c2 = _make_config()
        assert _compute_config_hash(c1) == _compute_config_hash(c2)

    def test_different_config_different_hash(self):
        c1 = _make_config(project_name="proj-a")
        c2 = _make_config(project_name="proj-b")
        assert _compute_config_hash(c1) != _compute_config_hash(c2)
