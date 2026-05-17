---
number: "182"
title: "gate_process lacks self-circuit-breaker for repeated identical crashes on same item"
severity: medium
status: implemented
kind: bug
author: opencode
date: "2026-05-17"
tags: [gate, crash-loop, observability, phase5]
related: ["139", "180", "181"]
---

## Symptom

In GR-036, two review items crash-looped for ~2h13m with 3253 identical
`CUSTOM_FIELD_VIOLATION` errors each. BC-181's budget guardrail prevents
unbounded **claim** cycling but the item remains permanently in `gating`
state — it is never transitioned to `cannot_proceed`. The idle detector
monitor only watches runner output, not gate output, so no alert fires.

## Root cause

`gate_loop()` catches every exception uniformly. When the same exception
fires on every attempt for a given work item, there is no detection of
"this is the Nth identical crash in a row" and no self-terminating behavior.

BC-181 stops the cycling at `attempt_threshold`, but leaves the item in a
permanent `gating` limbo. A production-ready circuit breaker should detect
N consecutive identical errors and transition the item to `cannot_proceed`
automatically.

## Proposed fix

Three options, in order of preference:

1. **Identical-error circuit breaker**: After N ≥ 2 consecutive
   `gate_process_error` exceptions with the same error class/message on the
   same work item, transition directly to `cannot_proceed` via
   `gate_escalation`. This requires the gate to call
   `sub.transition(work_item_id, "gate_escalation", ...)` instead of
   just releasing the claim.

2. **Maximum-attempt hard stop**: When `attempt_number > 2 *
   attempt_threshold`, force-transition to `cannot_proceed` regardless of
   error pattern. Simpler but less precise.

3. **Monitor-level detection**: Add gate-process heartbeat to the
   `agent_golden_run.py` wrapper's monitoring, treating continuous
   `gate_process_error` on the same work item as a danger signal. This
   addresses observability without fixing the root cause.

Option 1 is the most principled but requires care: the gate must only
escalate for crash-type errors (schema violations, unexpected exceptions),
not for legitimate gate failures (mypy errors, pytest failures).

## Acceptance criteria

- AC-1: Work item with N >= 3 consecutive identical `gate_process_error`
  exceptions is transitioned to `cannot_proceed` instead of remaining in
  `gating` indefinitely.
- AC-2: Legitimate gate failures (mypy, pytest, ruff) are NOT escalated
  to `cannot_proceed` — they continue cycling through `gate_fail` → `new`.
- AC-3: GR-037 (or successor) shows `gate_escalation` for crash-loop items
  and `gate_near_budget` as a soft-stop fallback.

## Severity rationale

Medium. BC-181 prevents the unbounded cycling, so production impact is
mitigated. The remaining gap is that items are left in `gating` limbo
permanently rather than being resolved. This is a pipeline completeness
issue, not a correctness or resource-exhaustion issue.

## Fix

Implemented Option 1 (identical-error circuit breaker).

`gate_loop()` now maintains a per-run dict `_crash_state` mapping
`work_item_id → (consecutive_crash_count, last_error_sig)` where
`error_sig = f"{type(exc).__name__}: {exc}"`. On each exception:

- If the error signature matches the previous one for that item, increment the
  consecutive count; otherwise reset to 1.
- When `count >= config.gate_crash_threshold` (default 3), call
  `sub.transition(work_item_id, TRANSITION_GATE_ESCALATION, ...)` directly
  and clear the counter. The item lands in `cannot_proceed`.
- Otherwise, release the claim as before and continue.
- On a successful `process_gate_item` call, clear the crash counter for that
  item (`_crash_state.pop`).

Legitimate gate failures (mypy, pytest, ruff) never raise exceptions from
`process_gate_item` — they are handled internally and produce a `gate_fail`
transition. The exception handler is therefore crash-only by construction
(AC-2 is structurally guaranteed, not just policy).

A new `gate_crash_threshold: int = 3` field was added to `FactoryConfig` to
make the threshold configurable without code changes.

## Touched surface

- `src/factory/config.py` — added `gate_crash_threshold: int = 3` to `FactoryConfig`
- `src/factory/gate_process.py` — circuit-breaker logic in `gate_loop()`
- `tests/test_gate_process_budget_and_field_validation.py` — 4 new tests in
  `TestGateCrashLoopCircuitBreaker`: identical crash escalation (AC-1),
  differing-error counter reset, success clears counter, legitimate gate fail
  no-raise (AC-2)
