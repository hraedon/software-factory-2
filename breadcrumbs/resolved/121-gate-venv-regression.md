---
number: "121"
title: "Gate process and runner use project venv instead of gate venv for gate tooling"
severity: critical
status: implemented
kind: bug
author: opencode-golden-run-015
date: "2026-05-11"
tags: [gate, runner, venv, bc-115, regression]
related: ["115", "118", "119"]
---

## Problem

BC-115 moved gate tooling (pytest, mypy, ruff) from the project venv to a separate `.venv-gate`. `_clean_stale_project_venv` removes gate tools from existing project venvs. However, both `gate_process.py` and `runner.py` continued to call `ensure_project_venv()` and use its returned python for all gate operations.

Result: when `use_project_venv: true`, the project venv has no gate tools, causing:
- Outer gate `evaluate_test_suite()` → `test_suite_collect` fails with "pytest not installed" (tool_not_found)
- Outer gate `evaluate_implementation()` → mypy/pytest fail with tool_not_found
- Inner gate `_run_ruff_fast()` → may fail if ruff was cleaned from project venv

GR-015 hit this on every test_suite: 0% lock rate, all 8 escalated to cannot_proceed.

## Root cause

`gate_process.py` line 156 and `runner.py` line 237 both do:

```python
python_executable = str(ensure_project_venv(runtime.workspace_root))
```

But `ensure_project_venv` returns the project venv python, which after BC-115 only has project requirements (e.g. `cryptography`), not gate tools.

## Fix

1. Made `_ensure_gate_venv` public as `ensure_gate_venv`
2. `ensure_gate_venv` now installs both `_GATE_TOOLS` AND project `requirements.txt` into `.venv-gate`
3. Hash includes both gate-tools hash and requirements hash so venv rebuilds when either changes
4. `gate_process.py` uses `ensure_gate_venv()` for `python_executable`
5. `runner.py` uses `ensure_gate_venv()` for inner-gate `python_executable`

## Affected files

- `src/factory/venv.py` — `ensure_gate_venv` (was `_ensure_gate_venv`), installs reqs too
- `src/factory/gate_process.py` — uses `ensure_gate_venv`
- `src/factory/runner.py` — uses `ensure_gate_venv` for pre-gate deps

## Verification

Simulated gate evaluation on a failing GR-015 test_suite artifact with fixed venv:
```
evaluate_test_suite(..., python_executable="/tmp/sf2-golden-015/.venv-gate/bin/python")
→ passed=True
```
