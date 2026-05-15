---
number: "RFC-018"
title: "Live state reporter — substrate-derived project snapshot"
severity: medium
status: implemented
kind: design
author: opencode-review
date: "2026-05-13"
tags: [telemetry, runner, scheduler, ops, phase-4]
related: ["033", "RFC-017", "RFC-008"]
phase_needed: "Phase 4 or Phase 5"
---

## Problem

v1 had `audit/state_report.py`, which produced a `STATE.yaml` snapshot: work item counts by stage, recent breadcrumb status, test counts, git history, and module docstrings — all in ~500 tokens designed for a new session to read in under a minute.

v2 has end-of-run telemetry (`telemetry.py`) but no equivalent "what's the project state *right now*?" command. The principal currently answers this question manually by running substrate queries or reading log tail. This is fine for golden runs but brittle for a long-running Phase 5 workload where the principal needs to know whether the pipeline is stuck, progressing, or finished without scrolling through log files.

## Scope

### In scope

A new command `factory state --config <yaml>` that prints a structured, human-readable snapshot derived entirely from substrate state (no new persistence):

**Section 1: Pipeline progress**
- Total work items by type (interface_spec, test_suite, implementation).
- Counts per state: new, in_progress, locked, cannot_proceed, stuck.
- Estimated completion percentage: `locked / (locked + in_progress + new)`.
- Mean time-in-state for in_progress items (stuck detector).

**Section 2: Recent gate activity**
- Gate failures in the last N events (default 50), grouped by `diagnostic_kind`.
- Top 3 failure classes with count and most recent instance.
- Unknown / tool_not_found rate (telemetry verify metric, live).

**Section 3: Channel & role health**
- Active role-to-channel bindings from config.
- Per-channel claim count and last-success timestamp.
- Consecutive failure count (from runner circuit breaker).

**Section 4: Disk & resource pressure**
- Workspace root size and `/tmp` size (advisory; delegates to RFC-017 if implemented).
- If RFC-017 not yet implemented, shows `du -sh` equivalent as plain text.

**Output formats:**
- Default: rich markdown table (terminal-friendly).
- `--json`: machine-readable for downstream scripting.
- `--brief`: one-line summary (`12/24 locked, 2 stuck, 0 disk pressure`).

### Out of scope

- Persistent dashboard or web UI (spec §7 mentions a dashboard but it is speculative).
- Prometheus metrics export (spec §7 mentions Prometheus but it is deferred).
- Real-time streaming updates (websocket, SSE). Polling is acceptable.

## Design

### New module: `factory/state_reporter.py`

```python
@dataclass
class PipelineSnapshot:
    project_name: str
    workflow_name: str
    workflow_version: int
    timestamp: datetime
    progress: ProgressSummary
    recent_failures: list[FailureSummary]
    channel_health: list[ChannelHealth]
    disk_pressure: DiskPressure | None

@dataclass
class ProgressSummary:
    total: int
    by_state: dict[str, int]
    completion_percent: float
    mean_time_in_progress_minutes: float | None

class StateReporter:
    def __init__(self, sub: Substrate, config: FactoryConfig): ...
    def snapshot(self) -> PipelineSnapshot: ...
    def render_markdown(self, snap: PipelineSnapshot) -> str: ...
```

### Integration

- **CLI entry point:** `python -m factory.state_reporter --config <yaml> [--json] [--brief] [--watch N]`
- **`--watch N`**: poll every N seconds and print brief line (for `tmux` window / terminal monitor).
- **Telemetry reuse:** `StateReporter` uses the same substrate queries as `telemetry.py` but aggregates differently (live counts vs. end-of-run metrics).
- **No substrate changes:** All data comes from existing `query_work_items`, `read_events`, and `read_events_composite` APIs.

### Performance

- Target: <2 seconds for a 100-work-item project on warm substrate connection.
- Query strategy: one `query_work_items` call (already paginated) + one `read_events` call with `event_type=gate_fail` and limit=50.
- If `--watch` is used, the reporter should cache the work-item list and only re-query events.

## Phase placement

Phase 4 (jury and race) or Phase 5. It is not a Phase 5 blocker — the principal can still tail logs — but it becomes essential once runs exceed ~1 hour.

## Validation criteria

1. `factory state --config golden-run-021-config.yaml --brief` prints a one-line summary.
2. `factory state --config golden-run-021-config.yaml --json` produces valid JSON with all `PipelineSnapshot` fields.
3. On a completed golden run, `completion_percent` equals the telemetry lock rate (±1 work item tolerance for pagination edge cases).
4. No new substrate API surface needed; all data from existing queries.

## Precedent

- v1 `factory/audit/state_report.py` — `STATE.yaml` generation with git history, test counts, breadcrumb status.
- v2 telemetry.py — substrate query patterns and aggregation logic are reusable.
