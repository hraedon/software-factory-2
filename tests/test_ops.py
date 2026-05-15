from __future__ import annotations

import os
import time
from pathlib import Path

from factory.config import OpsConfig
from factory.ops.cleanup import (
    CleanupResult,
    WorkspaceCleaner,
    _is_safe_path,
    cleanup_workspaces,
)
from factory.ops.disk_monitor import (
    DiskMonitor,
    check_disk_usage,
)
from factory.ops.log_rotation import configure_log_rotation
from factory.ops.resource_limits import (
    ResourceLimiter,
    check_resource_limit,
)


class TestCleanupSafePath:
    def test_allows_tmp(self):
        assert _is_safe_path(Path("/tmp/sf2-golden-001"))

    def test_allows_var_tmp(self):
        assert _is_safe_path(Path("/var/tmp/sf2-golden-001"))

    def test_rejects_home(self):
        assert not _is_safe_path(Path("/home/user/sf2-golden-001"))

    def test_rejects_project_dir(self):
        assert not _is_safe_path(Path("/projects/sf2-golden-001"))


class TestCleanupWorkspaces:
    def test_dry_run_lists_but_does_not_delete(self, tmp_path):
        ws = tmp_path / "sf2-golden-001"
        ws.mkdir()
        (ws / "file.txt").write_text("test")
        old_mtime = time.time() - 200 * 3600
        os.utime(ws, (old_mtime, old_mtime))

        result = cleanup_workspaces(
            root=tmp_path, config=OpsConfig(workspace_max_age_hours=168), dry_run=True
        )
        assert ws.exists()
        assert len(result.deleted_dirs) == 1
        assert "[dry-run]" in result.deleted_dirs[0]

    def test_deletes_expired_workspace(self, tmp_path):
        ws = tmp_path / "sf2-golden-001"
        ws.mkdir()
        (ws / "file.txt").write_text("test")
        old_mtime = time.time() - 200 * 3600
        os.utime(ws, (old_mtime, old_mtime))

        result = cleanup_workspaces(root=tmp_path, config=OpsConfig(workspace_max_age_hours=168))
        assert not ws.exists()
        assert str(ws) in result.deleted_dirs

    def test_preserves_recent_workspace(self, tmp_path):
        ws = tmp_path / "sf2-golden-001"
        ws.mkdir()
        (ws / "file.txt").write_text("test")

        result = cleanup_workspaces(root=tmp_path, config=OpsConfig(workspace_max_age_hours=168))
        assert ws.exists()
        assert str(ws) in result.preserved_dirs

    def test_preserves_corrupt_workspace(self, tmp_path):
        ws = tmp_path / "sf2-golden-001"
        ws.mkdir()
        (ws / ".corrupt").mkdir()
        old_mtime = time.time() - 200 * 3600
        os.utime(ws, (old_mtime, old_mtime))

        result = cleanup_workspaces(
            root=tmp_path,
            config=OpsConfig(workspace_max_age_hours=168),
        )
        assert ws.exists()
        assert str(ws) in result.preserved_dirs

    def test_skips_non_sf2_dirs(self, tmp_path):
        other = tmp_path / "other-dir"
        other.mkdir()

        result = cleanup_workspaces(root=tmp_path, config=OpsConfig())
        assert len(result.deleted_dirs) == 0
        assert len(result.preserved_dirs) == 0

    def test_nonexistent_root(self):
        result = cleanup_workspaces(root=Path("/nonexistent/path"))
        assert result.deleted_dirs == []
        assert result.errors == []

    def test_cleans_orig_files(self, tmp_path):
        orig = tmp_path / "module.py.orig"
        orig.write_text("old content")
        old_mtime = time.time() - 200 * 3600
        os.utime(orig, (old_mtime, old_mtime))

        result = cleanup_workspaces(root=tmp_path, config=OpsConfig(workspace_max_age_hours=168))
        assert not orig.exists()
        assert len(result.deleted_files) >= 1


class TestWorkspaceCleaner:
    def test_dry_run(self, tmp_path):
        ws = tmp_path / "sf2-golden-001"
        ws.mkdir()
        old_mtime = time.time() - 200 * 3600
        os.utime(ws, (old_mtime, old_mtime))

        cleaner = WorkspaceCleaner(OpsConfig(workspace_max_age_hours=168))
        result = cleaner.run(dry_run=True)
        assert isinstance(result, CleanupResult)


class TestDiskMonitor:
    def test_check_returns_results(self):
        results = check_disk_usage(paths=["/tmp"])
        assert len(results) >= 1
        assert results[0].level in ("ok", "warning", "error")
        assert results[0].usage.total_bytes > 0

    def test_warning_threshold(self):
        cfg = OpsConfig(disk_alert_warning_percent=0.0)
        results = check_disk_usage(paths=["/tmp"], config=cfg)
        assert any(r.level == "warning" for r in results)

    def test_nonexistent_path(self):
        results = check_disk_usage(paths=["/nonexistent"])
        assert len(results) == 0

    def test_disk_monitor_class(self):
        monitor = DiskMonitor(OpsConfig())
        results = monitor.check(["/tmp"])
        assert len(results) >= 1


class TestLogRotation:
    def test_creates_handler(self, tmp_path):
        log_file = tmp_path / "test.log"
        handler = configure_log_rotation(log_file)
        assert handler is not None
        assert handler.maxBytes == 10_000_000
        assert handler.backupCount == 5

    def test_custom_config(self, tmp_path):
        log_file = tmp_path / "test.log"
        cfg = OpsConfig(log_max_size_bytes=5000, log_backup_count=3)
        handler = configure_log_rotation(log_file, config=cfg)
        assert handler.maxBytes == 5000
        assert handler.backupCount == 3


class TestResourceLimits:
    def test_check_current_process(self):
        pid = os.getpid()
        result = check_resource_limit(pid, time.time() - 10)
        assert result.pid == pid
        assert result.memory_rss_mb > 0
        assert not result.exceeded

    def test_check_nonexistent_pid(self):
        result = check_resource_limit(99999999, time.time())
        assert not result.exceeded
        assert result.reason == "proc_unavailable"

    def test_resource_limiter_register_unregister(self):
        limiter = ResourceLimiter()
        limiter.register(12345)
        assert 12345 in limiter._start_times
        limiter.unregister(12345)
        assert 12345 not in limiter._start_times

    def test_resource_limiter_check_all(self):
        pid = os.getpid()
        limiter = ResourceLimiter(OpsConfig(max_memory_rss_mb=102400))
        limiter.register(pid)
        results = limiter.check_all()
        assert len(results) == 1
        assert not results[0].exceeded
