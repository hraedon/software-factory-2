---
number: "038"
title: test_suite gate doesn't verify pytest collectability — test-theater gap
severity: medium
status: resolved
kind: design
author: opencode
date: "2026-05-08"
tags: [gate, stage-3, stage-5, failure-routing]
related: []
resolution: "Added _run_pytest_collect() to evaluate_test_suite() — runs pytest --collect-only and fails on 0 collected tests or non-zero exit. TEST_COLLECT diagnostic kind reused from router."
---

## Problem

`evaluate_test_suite()` in `gate.py:168-226` checks file existence, emptiness, syntax, and forbidden imports. It does NOT verify that the file contains actual `test_` functions or that `pytest --collect-only` succeeds. A syntactically valid Python file with zero test functions (or only helper functions, no `test_*` names) passes the gate.

## Impact

This is a test-theater vector (spec §8.9 acknowledges the risk). The downstream consequences:

1. The implementation gate's `_run_pytest` would run `pytest` on an empty test suite — pytest exits 0 with "no tests collected" (exit code 5 with `-x`, but exit code 0 without). The implementation passes the pytest gate trivially.
2. The pipeline produces a "locked" implementation artifact that has never been tested against the ACs.
3. Only the frontier judge (Stage 6+) would catch this, and only if the jury is configured for the pipeline run. Phase 2 does not include a frontier judge.

The risk is mitigated by the test_author prompt quality (the worked example and explicit instructions produce good test files), but it's not structurally enforced by the gate.

## Proposed Fix

Add a `pytest --collect-only` subprocess check to `evaluate_test_suite()`. If pytest reports zero collected tests, the gate fails with a `TEST_COLLECT` diagnostic kind (already defined in the router's `_PHASE2_DISPATCH`). This is consistent with the implementation gate's pytest check.

The check should be gated on `shutil.which("pytest")` availability (same pattern as `_run_mypy` and `_run_pytest` in `evaluate_implementation`).

## Location

- `src/factory/gate.py:168-226` — `evaluate_test_suite()`
- `src/factory/router.py:20` — `TEST_COLLECT` diagnostic kind already exists
