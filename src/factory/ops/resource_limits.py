from __future__ import annotations

import logging
import os
import signal
import time
from dataclasses import dataclass

from factory.config import OpsConfig

_ops_log = logging.getLogger("factory.ops.resource_limits")

_MB = 1024 * 1024


@dataclass(frozen=True)
class ResourceCheckResult:
    pid: int
    memory_rss_mb: float
    elapsed_seconds: float
    exceeded: bool
    reason: str


def _get_rss_mb(pid: int) -> float | None:
    try:
        with open(f"/proc/{pid}/statm") as f:
            fields = f.read().split()
            rss_pages = int(fields[1])
            page_size = os.sysconf("SC_PAGE_SIZE")
            return (rss_pages * page_size) / _MB
    except (OSError, ValueError, IndexError):
        return None


def check_resource_limit(
    pid: int,
    start_time: float,
    config: OpsConfig | None = None,
) -> ResourceCheckResult:
    cfg = config or OpsConfig()
    elapsed = time.time() - start_time
    rss_mb = _get_rss_mb(pid)

    if rss_mb is None:
        return ResourceCheckResult(
            pid=pid,
            memory_rss_mb=0.0,
            elapsed_seconds=elapsed,
            exceeded=False,
            reason="proc_unavailable",
        )

    exceeded = rss_mb > cfg.max_memory_rss_mb
    reason = "memory" if exceeded else ""

    if exceeded:
        _ops_log.error(
            "resource_limit_exceeded pid=%d rss_mb=%.1f limit_mb=%d",
            pid,
            rss_mb,
            cfg.max_memory_rss_mb,
        )

    return ResourceCheckResult(
        pid=pid,
        memory_rss_mb=round(rss_mb, 1),
        elapsed_seconds=round(elapsed, 1),
        exceeded=exceeded,
        reason=reason,
    )


def terminate_gracefully(pid: int, grace_seconds: int = 5) -> None:
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        return
    deadline = time.time() + grace_seconds
    while time.time() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return
        time.sleep(0.5)
    try:
        os.kill(pid, signal.SIGKILL)
    except ProcessLookupError:
        pass


class ResourceLimiter:
    def __init__(self, config: OpsConfig | None = None):
        self.config = config or OpsConfig()
        self._start_times: dict[int, float] = {}

    def register(self, pid: int) -> None:
        self._start_times[pid] = time.time()

    def unregister(self, pid: int) -> None:
        self._start_times.pop(pid, None)

    def check_all(self) -> list[ResourceCheckResult]:
        results: list[ResourceCheckResult] = []
        for pid, start_time in list(self._start_times.items()):
            result = check_resource_limit(pid, start_time, self.config)
            if result.exceeded:
                terminate_gracefully(pid)
                self.unregister(pid)
            results.append(result)
        return results
