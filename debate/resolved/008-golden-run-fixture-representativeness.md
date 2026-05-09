---
number: "008"
title: "Golden-run fixture representativeness — do curated specs predict real LoB success?"
author: opencode
date: "2026-05-09"
related: ["RFC-008", "BC-063", "BC-068"]
---

## Context

v2's Phase 2 exit criteria are validated on 15 curated spec fixtures. Golden runs 001–005 exercise these fixtures with real model channels. Results:
- GR004 (Claude Sonnet): 12/15 implementations (80%)
- GR005 (Kimi k2.6): 13/15 implementations (87%)

The 15 fixtures are presumably self-contained, behavior-testable, and representative of line-of-business tooling. But what is the *distribution* of complexity in real LoB work? Factory's production data (Luke talk) shows:
- A Slack clone required 60% of time in implementation, 60% of tokens
- 50% of final LOC were tests
- 90% code coverage
- Multiple follow-up features created after initial validation
- Validation never succeeded on first pass

## Problem

The curated fixtures may be too small, too isolated, or too well-specified to predict success on real LoB work. If Phase 5 selects a workload that is:
- Multi-module (cross-work-item imports)
- Stateful (database, filesystem, external APIs)
- UI-driven (web app with forms, buttons, navigation)
- Integration-heavy (3+ modules must work together)

Then 87% on curated fixtures may drop to 30% on the real workload. The principal won't know until Phase 5 fails expensively.

## Position

**Before declaring Phase 2 complete, run at least one "adversarial" golden run with a deliberately complex fixture that matches real LoB characteristics.**

### What an adversarial fixture includes

1. **Multi-module dependency:** An `interface_spec` that declares 3+ modules with cross-imports. Tests in `test_suite` that exercise integration across modules. Implementation must wire them together.
2. **Stateful behavior:** The spec requires a database or filesystem operation. Tests verify state persistence across calls.
3. **Error taxonomy:** The spec declares 5+ error conditions. Tests must exercise each. Implementation must raise correct errors under correct conditions.
4. **UI component:** A simple web endpoint (FastAPI/Flask) with a form. The behavioral gate (Debate 001) exercises it via Playwright.
5. **AC ambiguity:** One acceptance criterion is intentionally vague. The system should either resolve it via orchestrator clarification or escalate to principal.

### Why this matters

Phase 2's current success metric is "80%+ pass rate on curated fixtures." But if the fixtures are unrepresentative, this metric is a vanity number. Factory's Slack clone is the reference point for what "real" means. v2 needs its own equivalent — even if it's just a toy CRUD app with a database.

### Alternative: calibrate fixture difficulty

Rate each of the 15 fixtures on:
- Lines of spec text
- Number of ACs
- Number of declared error conditions
- Number of cross-module dependencies
- Presence of I/O (network, filesystem, DB)

Compare the distribution to the Phase 5 target workload. If the target is 3σ from the fixture mean, add intermediate fixtures before Phase 5.

## Risks

| Risk | Mitigation |
|---|---|
| Adversarial fixture is too hard and kills morale | Set expectations: it's a calibration, not a pass/fail gate. Target 40% as acceptable |
| Building the adversarial fixture takes a session | Acceptable cost. One session now prevents a Phase 5 surprise |
| Real LoB work is too variable to fixture-ize | Use the adversarial fixture as a lower bound, not a predictor |

## Blocking

Phase 2 exit criteria. Should be completed before Phase 3 begins, because Phase 3 fleet integration is expensive and should not be tuned against unrepresentative workloads.

## Next step

1. Select one existing fixture and extend it to multi-module + stateful + UI
2. Run it as GR006 with the current best channel (Kimi k2.6 or Claude Sonnet)
3. Record pass rate, wall-clock, and escalation reasons
4. Compare to GR004/005. If the drop is >30 percentage points, add intermediate fixtures before declaring Phase 2 done
