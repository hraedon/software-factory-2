---
number: "079"
title: "Inner gate (pre_gate.py) silently passes on tool-not-found and exceptions — contradicts BC-059 fix scope, wastes model budget"
severity: high
status: resolved
kind: bug
author: deepseek-v4-pro (adversarial review — Session 20)
date: "2026-05-11"
tags: [gate, runner, stage-5]
related: ["059", "075"]
---

## Problem

BC-059 resolved gate soft-fail on missing tooling for the outer gate (`gate.py`). All four subprocess gates (pytest, mypy, ruff, pytest-collect) now return `passed=False, tool_not_found` when the tool is not installed. But the inner gate (`pre_gate.py`) was **not included** in that fix. The inner gate's tool-failure behavior diverges systematically:

| Tool failure | Outer gate (`gate.py`) | Inner gate (`pre_gate.py`) |
|---|---|---|
| ruff not found | `passed=False, tool_not_found` | Returns `{"passed": True}` (silent) |
| pytest not found | `passed=False, tool_not_found` | Returns `{"passed": True}` (silent) |
| Exception during ruff | `passed=False, impl_lint` | Returns `{"passed": True}` (bare `except` at line 210) |
| Exception during pytest | `passed=False, impl_pytest` | Returns `{"passed": True}` (silent) |

The specific code paths:
- `pre_gate.py:209`: `except Exception: return {"passed": True, "diagnostics": []}`
- `pre_gate.py:262-263`: `if "No module named pytest" in result.stderr: return {"passed": True, "diagnostics": []}`
- `pre_gate.py:169-170`: `if "No module named mypy" in result.stderr: return {"passed": True, "diagnostics": []}`

## Impact

When ruff or pytest are not installed in the environment the inner gate runs in, the pre-gate reports `passed=True`. The artifact proceeds to submission, hits the outer gate, and the outer gate correctly fails with `tool_not_found`. The implementer is re-invoked and produces another artifact. This repeats until escalation fires — the model gets **no chance to fix the issue** because the inner gate never surfaces the tool-not-found condition.

This directly contradicts the purpose of BC-075 (inner gate loop): early catch-and-fix to reduce budget waste. When tools are missing, the inner gate is a no-op, and every invocation is wasted budget.

## Root cause

BC-059 explicitly excluded inner gate functions from its scope. The `_run_ruff_fast`, `_run_pytest_fast`, and `_run_mypy_fast` functions in `pre_gate.py` were never updated to match the outer gate's tool-not-found handling.

## Proposed fix

Apply the same diagnostic shape from the outer gate to the inner gate:
1. `_run_ruff_fast`: when ruff not found or invocation fails with exception, return `{"passed": False, "diagnostics": ["ruff not installed"]}` or equivalent.
2. `_run_pytest_fast`: when pytest not found, return failure rather than `{"passed": True}`.
3. `_run_mypy_fast`: when mypy not found, return failure rather than `{"passed": True}`.
4. Remove the bare `except Exception: return {"passed": True}` catch-alls in favor of explicit failure propagation.
5. Add tests verifying that inner gate correctly fails when tools are missing.
