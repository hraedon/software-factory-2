---
number: "182"
title: "gate_process lacks self-circuit-breaker for repeated identical crashes on same item"
severity: medium
status: proposed
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
