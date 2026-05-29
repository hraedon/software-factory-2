---
number: "223"
title: "Golden-run RUNCARD status field not reconciled after run — audit trail self-contradicts (GR-047 runcard still says 'not yet run')"
severity: low
status: proposed
kind: improvement
author: claude-opus (review session)
date: "2026-05-29"
tags: [provenance, golden-runs, process]
related: []
---

## Symptom

`golden-run-047-RUNCARD.md` line 3 reads `**Status:** not yet run`, but GR-047 has executed: there is a completed `golden-run-047-log.md` and a commit (`7245ef3 GR-047: Web-service archetype ...`). The runcard and the log are separate artifacts and nothing in the golden-run protocol flips the runcard's status when the run completes, so the two documents contradict each other in the audit trail.

## Why it matters

The project's whole posture is epistemic/provenance integrity (RFC-030, RFC-033). A self-contradicting audit trail — even a benign status field — is exactly the kind of drift that erodes trust in the record and trips up the next agent reading the runcard for current state. Low severity (no functional impact), but it is a provenance-hygiene defect, not cosmetic.

## Root cause

RUNCARDs are authored *before* a run (they are the plan). The AGENTS.md golden-run protocol (Step 5: write the log; Step 6: commit) never instructs the agent to reconcile the runcard's `Status:` field afterward. So pre-run status text ("not yet run") survives into the post-run record.

## Proposed fix

Pick one, principal's call:

1. **Reconcile on completion** — add to AGENTS.md Step 6: flip the runcard `Status:` to `complete — see golden-run-NNN-log.md` (or `aborted — see ...`) as part of the commit that lands the log.
2. **Drop the field** — remove `Status:` from runcards entirely and let the existence of `golden-run-NNN-log.md` be the single source of truth for whether a run executed. Simpler; one fewer thing to keep in sync.

Recommendation: option 2 (the log is already the system of record; a status field on the plan is a second source of truth that will keep drifting).

## Instance fix applied

`golden-run-047-RUNCARD.md` status line corrected to reflect that the run completed (see `golden-run-047-log.md`). The systemic fix (AGENTS.md protocol change or field removal) remains open pending principal decision.

## Why this isn't the previous fix recurring

N/A — first instance of this defect shape (pre-run plan artifact not reconciled with post-run record).
