---
number: "186"
title: "BC-181 gate_near_budget soft-stop never hard-transitions, allowing indefinite acquire/release churn on items stuck in gating state"
severity: medium
status: proposed
kind: bug
author: claude
date: "2026-05-17"
tags: [gate, gate_loop, budget, BC-181, churn, substrate-load, phase5]
related: ["181", "182", "139"]
---

## Symptom

A work item that lands in `gating` state already at or above
`attempt_threshold` cycles in the gate process indefinitely:
`acquire_claim` → `gate_near_budget` warning → `release_claim`, every
`poll_interval_seconds` (5s default). The item never transitions to a
terminal state on its own.

In GR-037, implementation `cc11078f-78ea-4820-8f24-fc212a16ea79` hit a 600s
opencode channel timeout in the runner, was submitted to gating with a
failure diagnostic at attempt=3, and then cycled for ~3 hours, reaching
`attempt_number=1175` with 1172 logged `gate_near_budget` events and 1172
pairs of substrate `acquire_claim`/`release_claim` transitions, before being
manually escalated.

## Root cause

`gate_loop()` in `gate_process.py` (per the BC-181 fix) does:

```python
if claim.attempt_number >= config.attempt_threshold:
    log.warning("gate_near_budget", ...)
    sub.release_claim(wi.work_item_id, actor_id)
    continue
```

This is a **soft** stop: the claim is released, but the item stays in
`gating`. On the next poll, `query_work_items(state="gating")` returns it
again, gate_loop re-acquires (incrementing `attempt_number`), sees the
threshold breach, releases, and the cycle repeats.

BC-181's own writeup acknowledged this:

> Note: this is a soft circuit breaker, not a hard transition to
> cannot_proceed. A hard transition would require the gate to call
> `sub.transition(work_item_id, "gate_escalation", ...)`, but the semantics
> of that transition for gate-internal crashes (as opposed to legitimate
> gate failures) need more thought. The current fix prevents unbounded
> cycling; a future BC can add the hard transition.

GR-037 is that future BC. "Prevents unbounded cycling" was true only in the
narrow sense that no model credits burn and no gate work happens — but
substrate transitions, log volume, and `attempt_number` all grow without
bound, and the gate-process's effective polling capacity for legitimate
items is reduced (each stuck item costs one acquire/release per poll).

The BC-182 self-circuit-breaker (identical-error counter) **cannot** rescue
this case because the BC-181 guard returns before `process_gate_item()` ever
runs, so no exception is raised and no crash-count is incremented.

## Reproduction

In GR-037: any item that fails in the runner (channel timeout in this case)
and is submitted to gating while `attempt_number >= attempt_threshold` will
exhibit the cycle. cc11078f reached attempt=1175.

A focused test case: insert a work item into substrate with state=`gating`
and `attempt_number=3`, start gate_process, observe `gate_near_budget`
fire every 5s with `attempt_number` climbing on each cycle.

## Fix options

**Option A (recommended):** Have the BC-181 guard hard-transition the item
to `cannot_proceed` via `TRANSITION_GATE_ESCALATION` on first detection,
mirroring the BC-182 escalation path. This is consistent with the runner's
BC-139 behavior, which transitions runner-claimed items to `cannot_proceed`
on the same condition.

Risk: if there's a legitimate scenario where a gating item at
attempt_threshold should NOT be terminal (e.g. a future "retry budget reset"
feature), this forecloses it. None such exists today.

**Option B:** Add a deduplication TTL — only re-acquire a `gate_near_budget`
item if the previous release was >N minutes ago. Avoids the churn while
leaving the item in `gating` for inspection. Less clean than Option A but
preserves diagnostic state.

**Option C:** Have the runner-side path that submits an item to gating at
attempt_threshold transition it directly to `cannot_proceed` instead of to
`gating`. This is the upstream-of-symptom fix: the item should never have
been in `gating` to begin with.

## Acceptance criteria

- AC-1: Test verifies that gate_loop, when seeing an item in `gating` state
  at `attempt_number >= attempt_threshold` for the first time, transitions
  it to `cannot_proceed` (Option A) or, under Option B/C, refrains from
  re-acquiring within the suppression window.
- AC-2: GR-038 (or successor) exercising a runner-side channel timeout
  shows the stuck item reaching a terminal state without 1000+
  acquire/release cycles.
- AC-3: No regression in BC-181 / BC-182 test coverage.

## Touched surface

- `src/factory/gate_process.py` — gate_loop budget-check branch.
- New focused test in `tests/test_gate_process_budget_and_field_validation.py`
  or a new file under the same theme.

## Severity rationale

Medium. The current behavior:
- Does not crash; verify_passed=True in GR-037.
- Does not burn model credits.
- Does generate ~720 substrate transitions per hour per stuck item, which
  is observable (1172 events in one item across ~3 hours in GR-037) and
  could become problematic at higher fixture sizes or with multiple
  channel timeouts in one run.
- Pollutes telemetry counts and gate logs in ways that make legitimate
  diagnostics harder to read.

Not critical because runner-side timeouts are rare (1 in GR-037, 0 in
GR-036) and the cycling does not block legitimate gate work on other items.

## Notes

- The companion wrapper guardrail (`gate_fail_cross_family_review >= 3`
  fatal trip) was removed in commit `6913f19` because BC-180/185 made it
  obsolete. The BC-181 guard removal would similarly retire a once-needed
  defensive structure now that the underlying state machine is sound.
- Worth considering as part of a broader pass on gate_process error
  taxonomy: distinguish "item is unfit for further processing" (terminal)
  from "I can't process this right now" (transient, retryable).
