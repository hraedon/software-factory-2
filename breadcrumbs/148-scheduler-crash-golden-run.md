---
number: "148"
title: "Scheduler crashes with exit code 1 during golden run — blocks outcome_verification stage"
severity: high
status: proposed
kind: bug
author: agent
date: "2026-05-15"
tags: [scheduler, stage-5, golden-run, crash]
related: ["147", "139"]
---

## Summary

During GR-029 (Phase 5, cert-watch full DAG, 8 work items), the scheduler process exited with code 1 approximately 65 minutes into the run. The runner and gate processes continued, but no new downstream work items were created after the scheduler died. This prevented the `integration → outcome_verification` handoff from executing, leaving the Phase 5 chain incomplete.

## What we know

- Runner PID and gate PID survived; scheduler PID exited with code 1.
- The crash occurred after the jury stage had processed at least one item.
- Logs were auto-cleaned by `agent_golden_run.py` before post-mortem, so the traceback is lost.
- The scheduler log showed normal `handoff_created` events right before the crash.

## Hypotheses

1. **Unhandled exception in `_ensure_downstream_item()`** — The Phase 5 scheduler logic added `integration` and `outcome_verification` handoffs. A bug in the new `_downstream_has_field()` guard or link_type resolution could raise an unhandled exception.
2. **Substrate connection failure** — The scheduler polls substrate every N seconds; a transient disconnect that isn't caught could kill the loop.
3. **Logging / stdout pipe break** — The scheduler writes to `/tmp/gr029-scheduler.log`. If the file descriptor closed unexpectedly, a write could raise.

## Reproduction

Run `scripts/agent_golden_run.py` with `--config golden-run-029-config.yaml --fixtures tests/fixtures/cert-watch`. The crash is not deterministic — GR-028 (3-item mini) did not crash, GR-029 (8-item full) did. Size or timing may be a factor.

## Next steps

1. Re-run with `--no-cleanup` to preserve scheduler log for traceback.
2. Add `try/except` around the scheduler main loop to log exceptions before exit.
3. Review `_ensure_downstream_item()` for unhandled paths specific to Phase 5 handoffs (integration, outcome_verification).
