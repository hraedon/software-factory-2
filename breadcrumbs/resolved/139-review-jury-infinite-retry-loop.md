---
number: "139"
title: Review and jury gate failures never escalate — infinite retry loop consumes unbounded sessions
severity: critical
status: resolved
kind: bug
author: agent
date: "2026-05-14"
tags: [gate, runner, failure-routing, review, jury]
related: ["027", "037", "055", "062"]
---

## Summary

The router's `_ESCALATABLE_KINDS` set only includes mechanical gate failure kinds (mypy, pytest, lint, import, test collect/binding/import-forbidden). Review gate failures (`cross_family_review`) and jury gate failures (`jury`, `jury_quorum`) classify as `DiagnosticKind.GENERIC`, which is **not** escalatable. The runner's `claim_near_budget` log at `src/factory/runner.py:192` is only a warning — it does not stop the loop.

The result: review and jury work items that fail their gate cycle back to `new` state forever, with the runner re-invoking the model on every attempt.

## Evidence

GR-026 (full cert-watch, Phase 4, triple jury):
- Two review work items (`1ec0bd0a`, `dbdb908e`) looped to attempt 340+ before manual kill
- Each cycle: runner claims → invokes opencode → submits → gate fails `cross_family_review` → routes to `new` → repeat
- Hundreds of opencode sessions created (the "session explosion" the principal observed)
- Telemetry: mean attempts to lock 9.92 (target ≤2.0), 3 stuck items

## Root cause

`src/factory/router.py:148-156`:

```python
_ESCALATABLE_KINDS = {
    DiagnosticKind.IMPL_MYPY,
    DiagnosticKind.IMPL_PYTEST,
    DiagnosticKind.IMPL_LINT,
    DiagnosticKind.IMPL_IMPORT,
    DiagnosticKind.TEST_AC_BINDING,
    DiagnosticKind.TEST_COLLECT,
    DiagnosticKind.TEST_IMPORT_FORBIDDEN,
}
```

`cross_family_review`, `jury`, `jury_quorum`, `jury_disagree` failures all classify as `GENERIC` or fall through to the default `Route(target_state=STATE_NEW)`. They never hit the `attempt_number >= attempt_threshold` escalation check.

Additionally, `src/factory/runner.py:192-198` logs a warning but does not refuse the claim or release it. The runner continues to process the item regardless.

## Proposed fix

Two-part fix needed:

1. **Router**: Add review/jury-specific diagnostic kinds to `_ESCALATABLE_KINDS`, or add a blanket rule that any `GENERIC` gate failure beyond `attempt_threshold` escalates to `cannot_proceed`.

2. **Runner**: Enforce `attempt_threshold` as a hard stop — when `claim.attempt_number >= config.attempt_threshold`, release the claim and skip processing (or let the gate handle escalation alone).

Option (a) — add specific kinds — is more precise and avoids over-escalating deterministic failures. Option (b) — blanket rule — is simpler but risks escalating items that could recover with a fresh invocation.

Recommend option (a) with new diagnostic kinds for `CROSS_FAMILY_REVIEW` and `JURY_*` failures.

## Resolution

Implemented 2026-05-14 in the same session it was discovered (BC-139 was elevated from `proposed` to `resolved` before commit).

### Changes

1. **`src/factory/router.py`:**
   - Added `DiagnosticKind.CROSS_FAMILY_REVIEW` and `DiagnosticKind.JURY`.
   - `_classify_diagnostic()` now maps `diagnostic_kind="cross_family_review"` and `diagnostic_kind="jury"` to their respective kinds (previously fell through to `GENERIC`).
   - Added both kinds to `_PHASE2_DISPATCH` (route to `new` below threshold, like all other escalatable kinds).
   - Added both kinds to `_ESCALATABLE_KINDS`. At `attempt_number >= attempt_threshold`, review/jury failures now escalate to `cannot_proceed_seam` instead of cycling to `new` forever.

2. **`src/factory/runner.py`:**
   - `claim_near_budget` warning is now a **hard stop**. Runner releases the claim and skips to the next work item when `attempt_number >= attempt_threshold`. Prevents model budget burn while waiting for gate escalation.

3. **Tests:** 8 new tests in `test_router.py` (classification) and `test_router_phase2.py` (escalation behavior). 670 tests pass, 13 skipped, 0 lint errors.

### Validation

The fix prevents the exact GR-026 failure pattern: `cross_family_review` gate fail → `new` → re-claim → repeat. With the fix, at attempt 3 the gate process escalates to `cannot_proceed`, and the runner refuses to process the item beyond threshold even if the gate lags.
