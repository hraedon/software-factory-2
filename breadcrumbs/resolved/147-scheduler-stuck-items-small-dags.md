---
number: "147"
title: Scheduler stuck-item handling for small DAGs — review item orphaned in gating
severity: medium
status: resolved
kind: bug
author: kimi-k2.6
date: "2026-05-15"
tags: [scheduler, stage-8, stage-9, dep-v1-NNN]
related: ["145", "102"]
---

## Problem

In GR-028 (3-work-item mini fixture), one review item ended up in `gating` state with no downstream `outcome_verification` item ever created. The runner, gate, and scheduler went idle before the scheduler could spawn the next stage.

Observed state after telemetry:
- 12/13 items locked (92%)
- 1 review item stuck in `gating` state
- No `outcome_verification` items existed in the project
- Scheduler log showed repeated `create_work_item` errors (earlier bug, now fixed) but even after fix, small DAGs may not poll long enough for the full chain to complete.

## Root Cause Analysis

1. **Runner goes idle before scheduler creates downstream items.** The runner processes all available work items, submits them, and then goes idle. The scheduler, running in a separate process, may still be iterating through `stage_topology` handoffs. If the runner exits before the scheduler creates the next stage, that stage is never created.

2. **No stuck-item detection in scheduler.** The scheduler currently only creates downstream items when it sees a source item in `locked` state during its poll loop. There is no mechanism to:
   - Detect items stuck in `gating` or `in_progress` for too long
   - Retry or escalate stuck items
   - Continue polling until the DAG is fully resolved

3. **Small DAG amplification.** On a 3-item DAG, there are only 3 initial interface_spec items. Once those are locked, the scheduler creates test_suite items. Once those are locked, it creates implementation items, then review items, then jury items, then integration items, then outcome_verification items. Each stage requires a separate poll cycle. If the runner processes items faster than the scheduler polls, the pipeline can stall.

## Impact

- **Blast radius:** Limited to small fixtures (< 5 work items) where the runner finishes before the scheduler completes all handoffs.
- **Workaround:** Use larger fixtures (e.g., cert-watch-mini 5 items, cert-watch 8 items) where the runner never goes idle before the scheduler completes.
- **Silent failure:** The telemetry report shows "stuck items: 1" but does not identify which item or why.

## Proposed Fix

Three options, ordered by complexity:

### Option A: Scheduler `--once` / `--max-polls` flag (minimal)
Add a CLI flag `--max-polls N` or `--once` to the scheduler that processes one poll cycle and exits. The agent golden run wrapper can then run scheduler in a loop until no new items are created for M consecutive cycles. This keeps the scheduler simple while ensuring the full DAG is resolved.

### Option B: Stuck-item detection in scheduler (medium)
Add a `stuck_item_threshold_seconds` to `FactoryConfig`. In `scheduler_loop`, query for items in `gating` or `in_progress` state for longer than the threshold. If found:
- Log a warning with the item ID and state
- Optionally release the claim (if claimed) so the gate or runner can re-process it
- Do NOT create downstream items for stuck items (prevents cascade)

### Option C: DAG completion check in scheduler (most robust)
Track the "expected" total number of work items for the current project based on the fixture set and stage topology. The scheduler knows that 3 interface_spec items should eventually produce 3 test_suite + 3 implementation + 3 review + 1 jury + 1 integration + 1 outcome_verification = 15 items. Poll until the total item count reaches the expected number OR all items are in terminal states (locked/cannot_proceed).

## Resolution

Subsumed by BC-164 fix: scheduler now runs 3 drain cycles after SIGTERM to complete pending handoffs before exiting.

## Decision

**Defer to Phase 5 exit criteria.** The principal stated that GR-028 is a validation run, not a production workload. The stuck-item behavior is understood and workaround-able (use larger fixtures). Option A is the cheapest and can be implemented if GR-029 (cert-watch-mini) shows the same pattern.

If GR-029 shows 0 stuck items, close this as "medium — workaround exists, no production impact."
If GR-029 shows ≥1 stuck item, implement Option A (scheduler `--max-polls`) before the next golden run.

## Acceptance Criteria

- [ ] GR-029 telemetry shows stuck item count
- [ ] If stuck > 0, implement Option A and re-run
- [ ] If stuck == 0, close this breadcrumb with rationale

## References

- GR-028 log: `.factory/golden-run-028-log.md`
- Scheduler code: `src/factory/scheduler.py`
- Agent golden run wrapper: `scripts/agent_golden_run.py`
