---
number: "CLASS-021"
title: "Artifact Integrity and Immutability"
severity: critical
status: active
kind: defect-class
author: rfc-016-backfill
date: "2026-05-15"
tags: [artifact, immutability, forensics]
related: ["088", "103", "114", "154"]
---

## Shape

Model output artifacts are mutated in-place (by ruff --fix, by inner-gate retry overwrites, by quarantine) instead of being copied to a new location, destroying the original model output.

## Systemic cause

The pipeline writes artifacts to the workspace and then gates them. The gate needs to run tools that modify files (ruff --fix). There was no architectural principle of original-artifact immutability until BC-088/BC-114; before that, in-place mutation was the default.

## Systemic fix

BC-088: retries write to `ad/retry-{N}` subdirectory. BC-114: ruff runs on tempdir copies. BC-154: `_run_ruff_fast` is now side-effect-free. The pattern is established; new gates must follow it.

## Trigger condition

≥3 instances (current: 5). Systemic fix deployed.

## Promotion decision (2026-05-16, opus-4-7)

CLASS-021 has reached 5 instances, which meets the README promotion threshold (≥5 instances). Per the promotion rule, the reviewer must file an RFC or document why a systemic fix isn't worth pursuing. **Documenting (b): the systemic fix is already deployed.**

- BC-088 / BC-114 / BC-154 established the immutability pattern (retries in `ad/retry-{N}`, tempdir copies for ruff, side-effect-free `_run_ruff_fast`).
- BC-170 was not a *new* mutation vector — it was a missed *role registration*. The integrator role was added without wiring its non-Python artifact format into the 5-point registration surface (`_artifact_extension_for_role`, `_run_pre_gate`, `_inner_gate_label`, `DETERMINISTIC_GATES`, outer gate dispatch). Ruff was applied to a `.py`-named file containing JSON, which the side-effect-free `_run_ruff_fast` correctly mutated by quote-normalizing.
- The structural fix for the *registration* problem is **RFC-028** (per-role capability map), which collapses the 5-point surface into a single declaration so the next role can't recreate BC-170's failure mode.

**No new RFC required for CLASS-021 itself.** The instance count is now closed pending genuinely new mutation vectors. If a future BC introduces a *new* mutation path (not a registration miss), re-open the promotion question.

## Instances

| BC   | Symptom |
|------|---------|
| 088  | Inner gate retry overwrites original artifact in-place |
| 103  | quarantine_attempt uses os.replace which can clobber |
| 114  | pre_gate _run_ruff_fast mutates artifact file in-place |
| 154  | _run_ruff_fast modifies artifact in-place inside inner gate |
| 170  | Pre-gate ruff mutates integrator JSON artifact — quote normalization corrupts .py-wrapped JSON |