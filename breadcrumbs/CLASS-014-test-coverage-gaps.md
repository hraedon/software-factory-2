---
number: "CLASS-014"
title: "Test Coverage Gaps for Existing Code"
severity: high
status: active
kind: defect-class
author: rfc-016-backfill
date: "2026-05-15"
tags: [testing, coverage, integration]
related: ["006", "007", "011", "014", "019", "020", "022", "029", "031", "064", "081", "110", "117", "153"]
---

## Shape

A code path is production-reliant but has no test coverage or only stub/partial coverage, so regressions are detected only by full golden runs or not at all.

## Systemic cause

The project prioritized building the pipeline over testing it. Test coverage was added reactively (after bugs) rather than proactively. The test surface is dominated by unit tests with mock substrates; real-substrate integration tests are a small fraction. There is no coverage gate in CI.

## Systemic fix

Add a coverage threshold to CI. Require new code paths to carry at least one integration test (using InMemorySubstrate at minimum). The `make integration` target should grow to cover every `_main()` entry point.

## Trigger condition

≥5 instances (current: 14). Far past threshold.

## Instances

| BC   | Symptom |
|------|---------|
| 006  | MockSubstrate needed for CI-portable tests |
| 007  | Integration tests are stubs |
| 011  | Claim transition not asserted in worker loop tests |
| 014  | Resume path untested at integration level |
| 019  | Channel failure modes untested |
| 020  | Config YAML loading untested |
| 022  | Integration tests access substrate private API |
| 029  | Test suite coverage gap closure |
| 031  | Gate process/runner coverage stuck at 54% |
| 064  | No automated channel adapter integration tests |
| 081  | No criteria test for cert-watch full DAG |
| 110  | Missing adversarial/fuzz tests for channel output parsing |
| 117  | Scheduler pagination has no integration test |
| 153  | Three test files have conditionally-skipped assertions |