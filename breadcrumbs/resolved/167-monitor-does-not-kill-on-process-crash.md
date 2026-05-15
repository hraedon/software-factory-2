---
number: "167"
title: "agent_golden_run.py _monitor_logs does NOT exit when a pipeline process crashes — runner/gate burn budget after scheduler death"
severity: medium
status: resolved
kind: bug
author: agent
date: "2026-05-15"
tags: [golden-run, observability, scheduler]
related: ["148", "161", "162"]
---

## Summary

`_monitor_logs()` in `agent_golden_run.py:270-274` detects when a pipeline process exits unexpectedly (via `p.poll()`) and logs a warning, but does NOT exit the monitoring loop or kill the remaining processes. After the scheduler died in GR-029 (exit code 1), the runner and gate kept running, burning model budget against items that could never reach completion.

```python
# agent_golden_run.py:270-274
if procs:
    for p in procs:
        if p.poll() is not None:
            _warn(f"Process PID={p.pid} exited with code {p.returncode}")
            # ⬆ just warns — does NOT kill other processes, does NOT exit
```

After the warning, monitoring continues via idle detection (10 cycles with no new log lines = ~10 minutes). But the runner and gate are still producing new log lines (processing work items, running inner gates), so idle detection may never trigger promptly. The pipeline burns budget until the user manually intervenes or the runner completes its work-item queue and stops producing log lines.

## Evidence

GR-029 log: "PID=632460 (scheduler) exited with code 1 during the run... The runner and gate continued running, but no new downstream work items were created after the scheduler died."

The golden run log explicitly notes the runner and gate continued running after scheduler death. The monitoring guardrails were insufficient to detect this.

## Impact

- Unbounded model budget burn after scheduler crash — every claim, invocation, and inner gate retry is wasted.
- The outcome_verification stage is unreachable without scheduler running, but the runner processes integration items that can never transition to outcome_verification.

## Fix

Two changes:
1. When any process exits with non-zero code, kill the remaining processes and run telemetry immediately.
2. Log the process exit as a fatal error, not just a warning, so the golden run log captures the severity.
