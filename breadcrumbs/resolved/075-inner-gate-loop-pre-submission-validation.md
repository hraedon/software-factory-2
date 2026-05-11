---
number: "075"
title: "Inner gate loop — pre-submission mypy+ruff+pytest validation for implementer role"
severity: medium
status: implemented
kind: improvement
author: glm-5.1
date: "2026-05-10"
tags: [runner, gate, stage-4]
related: ["074"]
---

## Problem

When the implementer produces an artifact with mypy or ruff errors, the current flow is: produce → submit → gate fails → scheduler creates new attempt → re-derive context (with prior_failures) → re-invoke → submit → gate may pass or fail again. Each outer loop iteration costs 5-10 minutes of wall-clock time.

This is the "v1 treadmill" pattern — adding prompt rules to prevent each failure mode. A structural alternative is to let the model get fast feedback on its own output, like a human developer running `mypy` and `ruff` before committing.

## Resolution

Added pre-submission validation loop for the implementer role:

1. **`pre_gate.py`** (extended): `pre_gate_implementation()` now runs mypy, ruff, **and pytest** in short-circuit order (mypy → ruff → pytest) before submitting to substrate. Returns `PreGateResult` with pass/fail status for each check and combined diagnostics. Pytest is only run when mypy and ruff both pass, so the model doesn't receive redundant diagnostics from type errors that would also cause pytest failures. Pytest diagnostics are truncated to the last 3 lines of output to avoid flooding `prior_failures`.

2. **`runner.py`**: `_inner_gate_loop()` resolves `test_suite_path` from `custom_fields` via `PreGateDeps` NamedTuple (replaces the previous 3-tuple). The inner loop short-circuits: if mypy fails, ruff and pytest are skipped; if ruff fails, pytest is skipped. The `gate_name` in `FailureEntry` is now `inner_mypy`, `inner_ruff`, or `inner_pytest` based on which check failed.

3. **`PreGateResult`**: Added `pytest_passed: bool` field. `PreGateDeps` NamedTuple carries `interface_pyi_path`, `dep_paths`, `python_executable`, `test_suite_path`.

4. **`_copy_dependency_pyis`** promoted to public `copy_dependency_pyis` in `pre_gate.py`. `gate.py` imports from `pre_gate.py` instead of duplicating.

## Short-circuit rationale

Running mypy → ruff → pytest (skipping later checks on earlier failure) serves two purposes:

1. **Signal quality**: Pytest output on code that doesn't type-check is noisy. The model fixates on the wrong signal if it sees both a type error and a cascading pytest failure. By short-circuiting, each retry sends a single, focused diagnostic.

2. **Wall-clock bound**: Pytest is the slowest check (~30-120s). Skipping it when mypy or ruff already failed keeps inner-loop latency minimal.

## Results

GR010 showed the inner gate loop catching a ruff line-too-long error and retrying (visible in logs as `inner_gate_failed_retry`). The remaining `cannot_proceed` on FR-03 is a runtime logic bug (`leaf=None` in pytest) — exactly the class pytest-in-inner-loop should address. GR-011 will validate on the same fixture.

## Deferred work

RFC-009 (interactive debugging / tool-use inner loop) documents the next structural escalation if pytest-in-inner-loop is insufficient after three golden runs of evidence.