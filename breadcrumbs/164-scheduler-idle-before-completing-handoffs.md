---
number: "164"
title: "Scheduler may go idle before completing all stage handoffs — outcome_verification unreachable on small DAGs"
severity: medium
status: proposed
kind: design
author: agent
date: "2026-05-15"
tags: [scheduler, stage-9, stage-topology]
related: ["147"]
---

## Summary

In GR-028 (3-item phase5-mini fixture), the integration item locked but no outcome_verification item was created. The scheduler iterates all handoffs per poll cycle (scheduler.py:48-63), but the runner may go idle before the scheduler processes the final handoff for deep DAGs.

The root cause is architectural: the runner and scheduler are independent processes. The runner sees a `locked` work item and looks for the next `new` item to claim. If the scheduler hasn't created the next `new` item yet (because it still needs another poll cycle), the runner goes idle and the pipeline stalls.

This is a known issue (BC-147 — scheduler stuck-item handling for small DAGs) but with a specific twist: even without stuck items, the scheduler can fail to complete deep chains on small fixtures because the runner processes items faster than the scheduler creates downstream items.

## Evidence

- GR-028: 13 pipeline items, 12 locked, outco me_verification never created. Config had `poll_interval_seconds: 5`, with 6 handoffs in `stage_topology`.
- GR-029: 24 pipeline items, 21 locked, outcome_verification never created (scheduler crashed, but even without the crash, the deep chain had 7 handoffs).

The scheduler's `_ensure_downstream_item` creates exactly one downstream item per handoff per poll cycle. For a 6-handoff chain with 8 source items, the scheduler needs 48 create operations spread across multiple poll cycles. If the runner claims and completes items faster than `6 × 5s = 30s` per wave, it will go idle before all downstream items are created.

## Impact

- Outcome verification is systematically unreachable on small DAGs without a runner-scheduler coordination mechanism.
- The deep-stage topology (7 handoffs in Phase 5) magnifies this problem — more stages mean more poll cycles needed to create the full chain.
- Testing Phase 5 requires artificially slowing the runner or running the scheduler `--once` with explicit wave control.

## Fix

Options:
1. **Scheduler-driven wave control** — Instead of passive polling, the scheduler should create ALL downstream items in one pass before releasing items to the runner.
2. **Run scheduler `--once` mode** — Create all items at once via `populate_work_items --create-downstream`, then let the runner process them all.
3. **Runner checks for new items after processing** — Add a `time.sleep(0)` to yield the scheduler a chance to create items between claims.
