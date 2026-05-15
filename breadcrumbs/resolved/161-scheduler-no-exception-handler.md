---
number: "161"
title: "Scheduler main loop has no exception handler — unhandled crash kills pipeline silently"
severity: high
status: resolved
kind: bug
author: agent
date: "2026-05-15"
tags: [scheduler, crash, stage-5]
related: ["148"]
---

## Summary

`scheduler_loop()` in `scheduler.py:32-63` has no top-level `try/except` around the poll loop. If `_ensure_downstream_item()` raises an unhandled exception (e.g., substrate API error, type mismatch in Phase 5 handoff logic, malformed link type), the entire scheduler process exits without logging the error.

```python
# scheduler.py:48-63 — no exception handling
while not shutting_down:
    for handoff in config.stage_topology:
        page = sub.query_work_items(...)
        for wi in page.items:
            if wi.work_item_type != handoff.source_type:
                continue
            _ensure_downstream_item(runtime, wi, handoff)  # could raise
    if not shutting_down:
        time.sleep(poll_interval)
```

In GR-029, the scheduler exited with code 1, preventing the `integration → outcome_verification` handoff. The root cause is unknown because logs were auto-cleaned before forensics.

Compare with `gate_process.py` which has a try/except in its poll loop (`process_gate_item` — the gate loop captures exceptions and continues).

## Evidence

GR-029 log: "Scheduler crashed (exit code 1) before creating outcome_verification downstream items... Root cause unknown — logs were auto-cleaned before inspection."

## Impact

- The outcome_verification stage is unreachable if the scheduler dies mid-run.
- Runner and gate processes continue unaware, burning model budget on items that will never reach terminal state.
- No exception traceback survives to help debugging.

## Fix

Wrap the scheduler poll loop body in `try/except Exception` that logs the exception and continues, or at minimum logs the traceback before re-raising.
