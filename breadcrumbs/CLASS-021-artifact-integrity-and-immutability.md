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

≥3 instances (current: 4). Systemic fix deployed.

## Instances

| BC   | Symptom |
|------|---------|
| 088  | Inner gate retry overwrites original artifact in-place |
| 103  | quarantine_attempt uses os.replace which can clobber |
| 114  | pre_gate _run_ruff_fast mutates artifact file in-place |
| 154  | _run_ruff_fast modifies artifact in-place inside inner gate |