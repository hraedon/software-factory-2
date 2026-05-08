---
number: "059"
title: "Gate returns passed=True when pytest/mypy/ruff not in PATH — silent no-op"
severity: critical
status: implemented
kind: bug
author: adversarial-reviewer
date: "2026-05-08"
tags: [gate, stage-5, runner]
related: ["055"]
---

## Summary

`_run_pytest_collect`, `_run_mypy`, `_run_pytest`, and `_run_ruff` in `gate.py` all return `passed=True` when `shutil.which()` finds no binary. Four call sites:

1. `_run_pytest_collect` line 339: `return GateResult(passed=True, ...)` when `pytest` not found
2. `_run_mypy` line 397: `return GateResult(passed=True, ...)` when `mypy` not found
3. `_run_pytest` line 446: `return GateResult(passed=True, ...)` when `pytest` not found
4. `_run_ruff` line 504: `return GateResult(passed=True, ...)` when `ruff` not found

In any environment where these binaries are missing from PATH (wrong venv, container misconfiguration, PATH poisoning), every single implementation passes all gates with zero tests run and zero type checking. The system reports 100% success while producing completely unverified code.

This directly violates Principle 5: "Mechanical gates over LLM gates wherever possible."

## Fix applied in this session

All four soft-fails now return `passed=False` with `diagnostic_kind="tool_not_found"`. Added `DiagnosticKind.TOOL_NOT_FOUND` enum member and `_PHASE2_DISPATCH` entry routing to `STATE_CANNOT_PROCEED` (terminal — retrying won't fix a missing binary).

## Affected tests

Tests in `test_gate_implementation_subprocess.py` use `@pytest.mark.skipif(not shutil.which(...))` to skip when tools are absent, so they are unaffected by this change. No test relied on the soft-fail behavior.

## Verification

- Run `make test` — all existing tests should pass
- Confirm `DiagnosticKind.TOOL_NOT_FOUND` appears in dispatch completeness test in `test_router_phase2.py`
