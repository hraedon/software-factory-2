---
number: "153"
title: "Three test files have conditionally-skipped assertions — silently pass without testing"
severity: high
status: resolved
kind: bug
author: agent
date: "2026-05-15"
tags: [testing, gate]
related: []
---

## Summary

Three test files use `if result.passed:` or `if not result["passed"]:` guards that skip assertions when the result doesn't match the expected failure mode. The tests appear to run but assert nothing.

**File:** `test_gate_implementation_subprocess.py:99-102`
```python
result = evaluate_implementation(impl_path)
if not result.passed and result.gate_name == GATE_NAME_IMPLEMENTATION_LINT:
    assert result.diagnostic_kind == "impl_lint"
    assert len(result.diagnostics) > 0
```
If `result.passed is True` (e.g., ruff is not installed and the gate passes vacuously, or ruff is installed and the code is actually fine), the `if` body is skipped and the test passes without asserting anything.

**File:** `test_pre_gate.py:218-219`
```python
result = _run_mypy_fast(...)
if not result["passed"]:
    assert any("mypy" in d.lower() for d in result["diagnostics"])
```

**File:** `test_pre_gate.py:233-235`
```python
result = _run_pytest_fast(...)
if not result["passed"]:
    assert ...
```

## Impact

- CI passes even when gate failure detection logic is broken.
- A regression in `evaluate_implementation` that makes it always return `passed=True` would not be caught by these tests.
- The tests are particularly dangerous because they *look* like they're testing failure paths, but they silently skip the assertions on success.

## Fix

Replace `if not result.passed:` with `assert not result.passed` (or `assert result["passed"] is False`). The test should unconditionally assert the failure case, not conditionally skip when the code changes behavior.
