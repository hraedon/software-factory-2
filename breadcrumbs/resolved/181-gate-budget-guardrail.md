---
number: "181"
title: "gate_process has no attempt budget guardrail — crash-looping items cycle indefinitely"
severity: high
status: implemented
kind: bug
author: opencode
date: "2026-05-17"
tags: [gate, budget, crash-loop, phase5]
related: ["139", "180"]
---

## Symptom

`gate_loop()` in `gate_process.py` catches `Exception` on every
`process_gate_item()` call, releases the claim, and continues to the next
polling cycle. If the same exception fires on every attempt (e.g.,
`CUSTOM_FIELD_VIOLATION` from BC-180), the work item's `attempt_number`
increments on every `acquire_claim` but never triggers a budget stop.

The runner's `claim_near_budget` guardrail (BC-139) only applies to
runner-claimed work items (in `new` or `in_progress` states). Gate-claimed
items in `gating` state have no equivalent protection.

## Root cause

No attempt-number check in `gate_loop`. Regista increments the attempt
counter on every `acquire_claim`, but `gate_loop` never queries it.

## Fix

Added a budget check at the top of the `for wi in page.items` loop in
`gate_loop()`, mirroring the runner's `claim_near_budget` pattern:

```python
if claim.attempt_number >= config.attempt_threshold:
    log.warning("gate_near_budget", ...)
    sub.release_claim(wi.work_item_id, actor_id)
    continue
```

Items at or above the attempt threshold are skipped with a warning log.
They remain in `gating` state but consume no further gate-process resources.

Note: this is a **soft** circuit breaker, not a hard transition to
`cannot_proceed`. A hard transition would require the gate to call
`sub.transition(work_item_id, "gate_escalation", ...)`, but the semantics
of that transition for gate-internal crashes (as opposed to legitimate gate
failures) need more thought. The current fix prevents unbounded cycling; a
future BC can add the hard transition.

## Acceptance criteria

- AC-1: `TestGateBudgetGuardrail::test_attempt_threshold_blocks_over_budget_items`
  verifies that items at `attempt_number >= attempt_threshold` are not
  processed by the gate.
- AC-2: GR-037 (or successor) shows `gate_near_budget` log entries instead
  of crash-looping.

## Touched surface

- `src/factory/gate_process.py` — added budget check in `gate_loop()`.
- `tests/test_gate_process_budget_and_field_validation.py` — 2 budget
  guardrail tests.

## Severity rationale

High. Without this fix, a single schema-violating crash-loop (like BC-180)
runs indefinitely until manual SIGTERM. With the fix, the item is left in
`gating` state with a logged warning. Not critical because BC-180's field
filter prevents the crash-loop from recurring, but both fixes are needed
for defense in depth.
