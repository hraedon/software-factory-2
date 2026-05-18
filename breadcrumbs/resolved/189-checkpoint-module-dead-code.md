---
number: "189"
title: "src/factory/checkpoint.py is dead code; RFC-008 unfulfilled or cancelled"
severity: medium
status: implemented
kind: bug
author: claude
date: "2026-05-18"
tags: [dead-code, runner, recovery, rfc-008]
related: []
---

# BC-189 — Checkpoint module is dead; resume path silently absent

## Problem

`src/factory/checkpoint.py` (≈221 lines) is not imported from anywhere under `src/` or `scripts/`:

```
$ grep -r "from factory.checkpoint\|import.*factory.checkpoint" src/ scripts/
(no matches)
$ grep -r "from factory.checkpoint" tests/
tests/test_checkpoint.py:6:from factory.checkpoint import (...)
```

Only the test file consumes the module. `can_resume_from_checkpoint`, `load_checkpoint`, etc. are never invoked by the runner.

Two consequences:

1. **The resume capability promised by RFC-008 is unimplemented in production.** A crash mid-run cannot be resumed; the module gives a false impression in the file tree.
2. **The module's stage taxonomy is stale.** The stage list in `checkpoint.py` (the `Phase-2 stages` enum at L119–123 in the current revision) omits review, jury, integration, and outcome_verification — stages added in Phase 3/4/5. Even if the runner started calling into it, restart logic would reason about a pipeline shorter than reality.

This is RFC-016's "obsolete safety mechanism" pattern (cf. RFC-033 guardrail lifecycle) one floor up: a *feature* that survived past its precondition becoming relevant.

## Proposed action (decide one)

- **A. Delete the module and `tests/test_checkpoint.py`.** Mark RFC-008 obsolete with a pointer here. Cleanest if no consumer needs resume today.
- **B. Wire `checkpoint.py` into the runner**, update the stage taxonomy to the full Phase-5 set, and re-validate RFC-008.
- **C. Keep the module, mark it experimental**, and add a CI check that fails if a non-test import isn't added by date D. (Discouraged — defers the decision without forcing it.)

Recommendation: **A** unless an explicit Phase-5 resume requirement exists. Carrying dead modules in a 1,000+ file codebase is how RFC-016 / CLASS-016 happen.

## Acceptance criteria

1. Decision recorded inline; RFC-008 status updated accordingly.
2. If A: module + test deleted; CI green.
3. If B: runner test demonstrates resume from a synthesized crash mid-Phase-5; stage list matches `spec.md` §4.

## Resolution

Option A chosen. Deleted `src/factory/checkpoint.py` and `tests/test_checkpoint.py`. RFC-008 marked obsolete — the module was never wired into production; the runner's existing idempotency on restart (artifact-level resumption via prior attempt scanning) is the actual recovery mechanism. No consumer outside tests imported the module.
