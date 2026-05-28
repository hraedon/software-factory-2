---
number: "RFC-017"
title: "Operational survivability — resource limits, disk monitoring, log rotation, and workspace lifecycle"
severity: high
status: implemented
kind: design
author: opencode-review
date: "2026-05-13"
tags: [ops, runner, gate, scheduler, phase-5, dep-v1-277]
related: ["RFC-008", "096", "RFC-019"]
phase_needed: "Phase 5 (first real workload)"
---

## Problem

v2 currently has no operational survivability layer. The evidence:

- **21 golden-run directories** (~600 MB) persist indefinitely in `/tmp/` with no automatic cleanup.
- **No log rotation** — runner, gate, and scheduler logs (when captured via shell redirection) grow unbounded.
- **No disk monitoring** — a long-running Phase 5 workload could exhaust `/tmp` or the project volume silently.
- **No process resource limits** — a runaway model subprocess could consume all memory or CPU.

v1 solved this with `factory/ops/resource_limits.py`, `disk_monitor.py`, `log_rotation.py`, and `cleanup.py` (BC-277). v2 does not need a full port, but Phase 5 (a real workload running for hours, not a 30-minute golden run) will fail without the minimal viable subset.

## Scope

### In scope (minimal viable ops layer)

1. **Workspace lifecycle / cleanup** (`factory/ops/cleanup.py`)
   - Configurable retention: `workspace_max_age_hours`, `archive_before_delete`.
   - Safe deletion with prefix whitelist (same as `populate_work_items.py --reset`).
   - Preserve checkpointed or recently-failed workspaces.
   - Triggered by scheduler post-handoff or by a `factory cleanup --dry-run` CLI.

2. **Log rotation** (`factory/ops/log_rotation.py`)
   - `RotatingFileHandler` configuration for runner, gate_process, and scheduler.
   - Config: `log_max_size_bytes`, `log_backup_count`, `log_max_age_hours`.
   - Not a custom rotator — use Python's standard library.

3. **Disk monitoring** (`factory/ops/disk_monitor.py`)
   - Periodic check of `workspace_root` and `/tmp` usage.
   - Threshold alerts at 80% (warning) and 90% (error) — emitted as structlog events.
   - Projected "hours until full" based on growth rate across last N runs.
   - No blocking action; the alert is advisory. The response is the cleanup module.

4. **Resource limits** (`factory/ops/resource_limits.py`)
   - Per-work-item memory RSS cap (via `resource` module or `psutil` if available).
   - Per-work-item wall-clock timeout (already exists at channel level; extend to subprocess gates).
   - Optional: CPU time soft limit for gate subprocesses.
   - Graceful kill on violation (SIGTERM → SIGKILL after grace period).

### Cleanup targets (explicit)

The cleanup module must handle:
- **Golden-run workspace directories** (`/tmp/sf2-golden-*`) older than `workspace_max_age_hours`.
- **`.orig` backup files** produced by ruff auto-fix (`inner_ruff` gate) — accumulate at thousands per day in a real workload.
- **Quarantined `.corrupt/` directories** — never auto-deleted; moved to an archive after `preserve_failed_hours`.
- **Log files** older than `log_max_age_hours` or exceeding `log_backup_count`.

### Out of scope (future phases)

- Full v1 `AdvancedLogRotator` with gzip compression and age-based cleanup.
- Cross-machine resource tracking or distributed fleet health monitoring.
- Kubernetes-style resource quotas or cgroup integration.
- Archive restoration UI.

## Design

### Integration points

| Module | Integration | Notes |
|---|---|---|
| `runner.py` | Uses resource limiter to wrap channel invoke | Kill runaway model subprocess |
| `gate.py` / `pre_gate.py` | Wraps subprocess gates with timeout + memory cap | Prevents gate-venv explosions |
| `scheduler.py` | Calls cleanup workspace prune after stage handoff | Keeps disk bounded between stages |
| `telemetry.py` | Reads disk-monitor JSONL for fleet-health reports | "Disk pressure" column in state reporter |
| `config.py` | Gains `OpsConfig` dataclass with retention knobs | All defaults live in `FactoryConfig` per AGENTS.md |

### Configuration

```python
@dataclass
class OpsConfig:
    workspace_max_age_hours: int = 168          # 7 days
    archive_before_delete: bool = True
    preserve_failed_hours: int = 24
    log_max_size_bytes: int = 10_000_000        # 10 MB
    log_backup_count: int = 5
    log_max_age_hours: int = 168
    disk_alert_warning_percent: float = 80.0
    disk_alert_error_percent: float = 90.0
    max_memory_rss_mb: int = 2048               # per work-item subprocess
    gate_subprocess_timeout_multiplier: float = 1.5  # of configured gate timeout
```

All fields are optional; if absent, the default above applies. No bare strings in function bodies.

### Safety invariants

1. Cleanup never deletes a workspace outside `/tmp`, `/var/tmp`, or the configured `workspace_root`.
2. Cleanup never deletes workspaces with active claims (checked via regista `in_progress` state).
3. Log rotation never deletes the final `*.log` file — only rotates when size exceeds threshold.
4. Resource limiter emits a regista event (`event_type="resource_limit_exceeded"`) before killing, so telemetry can classify the failure.

## Dependencies

- `psutil` is optional. If not installed, memory RSS limits are skipped with a warning.
- No regista changes required for Phase 5 MVP.

## Phase placement

Phase 5 prerequisite. Golden runs do not need this (they are short, hand-run, and `--reset` cleans up). A real workload does.

## Open questions

1. Should disk monitoring run in-process (scheduler tick) or as a background thread? Background thread is simpler but harder to test.
2. Should resource limits be per-work-item or per-role? Per-work-item is simpler; per-role allows stricter limits for implementer (larger artifacts) vs. interface architect.
3. Should workspace cleanup be synchronous (blocking scheduler handoff) or async (fire-and-forget)? Recommend sync for Phase 5; async adds complexity without proven need.

## Precedent

- v1 BC-277: "Ops module consolidation — resource limits, disk monitor, log rotation, cleanup moved to `factory/ops/` with CLI commands."
- v1 disk_monitor JSONL history format can be reused for trend projection.
