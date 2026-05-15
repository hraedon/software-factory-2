from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from pathlib import Path

from factory.config import OpsConfig

_ops_log = logging.getLogger("factory.ops.disk_monitor")


@dataclass(frozen=True)
class DiskUsage:
    total_bytes: int
    used_bytes: int
    free_bytes: int
    used_percent: float


@dataclass(frozen=True)
class DiskCheckResult:
    path: str
    usage: DiskUsage
    level: str
    hours_until_full: float | None


def _get_disk_usage(path: Path) -> DiskUsage:
    usage = shutil.disk_usage(str(path))
    used_percent = (usage.used / usage.total) * 100 if usage.total > 0 else 0
    return DiskUsage(
        total_bytes=usage.total,
        used_bytes=usage.used,
        free_bytes=usage.free,
        used_percent=round(used_percent, 1),
    )


def check_disk_usage(
    paths: list[Path | str] | None = None,
    config: OpsConfig | None = None,
) -> list[DiskCheckResult]:
    cfg = config or OpsConfig()
    check_paths = paths or ["/tmp", "/var/tmp"]
    results: list[DiskCheckResult] = []

    for p in check_paths:
        path = Path(p)
        if not path.exists():
            continue
        usage = _get_disk_usage(path)
        if usage.used_percent >= cfg.disk_alert_error_percent:
            level = "error"
        elif usage.used_percent >= cfg.disk_alert_warning_percent:
            level = "warning"
        else:
            level = "ok"

        result = DiskCheckResult(
            path=str(path),
            usage=usage,
            level=level,
            hours_until_full=None,
        )
        results.append(result)

        if level == "error":
            _ops_log.error(
                "disk_pressure path=%s used_percent=%.1f free_bytes=%d",
                path,
                usage.used_percent,
                usage.free_bytes,
            )
        elif level == "warning":
            _ops_log.warning(
                "disk_pressure path=%s used_percent=%.1f free_bytes=%d",
                path,
                usage.used_percent,
                usage.free_bytes,
            )

    return results


class DiskMonitor:
    def __init__(self, config: OpsConfig | None = None):
        self.config = config or OpsConfig()

    def check(self, paths: list[Path | str] | None = None) -> list[DiskCheckResult]:
        return check_disk_usage(paths, self.config)
