from __future__ import annotations

import logging
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from factory.config import OpsConfig

_ops_log = logging.getLogger("factory.ops.cleanup")

_ALLOWED_PREFIXES = ("/tmp", "/var/tmp")
_SF2_GOLDEN_PREFIX = "sf2-golden-"
_ORIG_SUFFIX = ".orig"


@dataclass(frozen=True)
class CleanupResult:
    deleted_dirs: list[str]
    deleted_files: list[str]
    preserved_dirs: list[str]
    errors: list[str]


def _is_safe_path(path: Path) -> bool:
    resolved = str(path.resolve())
    return any(resolved.startswith(prefix) for prefix in _ALLOWED_PREFIXES)


def _is_active_workspace(path: Path, preserve_failed_hours: int) -> bool:
    age_hours = (time.time() - path.stat().st_mtime) / 3600
    if age_hours < preserve_failed_hours:
        return True
    corrupt_dir = path / ".corrupt"
    if corrupt_dir.exists():
        return True
    return False


def cleanup_workspaces(
    root: Path | None = None,
    config: OpsConfig | None = None,
    dry_run: bool = False,
) -> CleanupResult:
    cfg = config or OpsConfig()
    search_root = root or Path("/tmp")
    deleted_dirs: list[str] = []
    deleted_files: list[str] = []
    preserved_dirs: list[str] = []
    errors: list[str] = []

    if not search_root.exists():
        return CleanupResult(deleted_dirs, deleted_files, preserved_dirs, errors)

    for entry in sorted(search_root.iterdir()):
        name = entry.name
        if not name.startswith(_SF2_GOLDEN_PREFIX):
            continue
        if not _is_safe_path(entry):
            preserved_dirs.append(str(entry))
            continue
        if not entry.is_dir():
            continue

        age_hours = (time.time() - entry.stat().st_mtime) / 3600
        if age_hours < cfg.workspace_max_age_hours:
            preserved_dirs.append(str(entry))
            continue

        corrupt_dir = entry / ".corrupt"
        if corrupt_dir.exists():
            preserved_dirs.append(str(entry))
            continue

        if cfg.archive_before_delete and not dry_run:
            _ops_log.info("archive_and_delete path=%s", entry)

        if dry_run:
            deleted_dirs.append(f"[dry-run] {entry}")
        else:
            try:
                shutil.rmtree(entry)
                deleted_dirs.append(str(entry))
            except OSError as exc:
                errors.append(f"{entry}: {exc}")

    orig_count = _cleanup_orig_files(search_root, cfg, dry_run)
    deleted_files.extend(orig_count)

    return CleanupResult(deleted_dirs, deleted_files, preserved_dirs, errors)


def _cleanup_orig_files(root: Path, config: OpsConfig, dry_run: bool) -> list[str]:
    deleted: list[str] = []
    if not root.exists():
        return deleted
    for entry in root.rglob(f"*{_ORIG_SUFFIX}"):
        age_hours = (time.time() - entry.stat().st_mtime) / 3600
        if age_hours < config.workspace_max_age_hours:
            continue
        if dry_run:
            deleted.append(f"[dry-run] {entry}")
        else:
            try:
                entry.unlink()
                deleted.append(str(entry))
            except OSError as exc:
                _ops_log.warning("orig_delete_failed path=%s error=%s", entry, exc)
    return deleted


class WorkspaceCleaner:
    def __init__(self, config: OpsConfig | None = None):
        self.config = config or OpsConfig()

    def run(self, dry_run: bool = False) -> CleanupResult:
        return cleanup_workspaces(config=self.config, dry_run=dry_run)
