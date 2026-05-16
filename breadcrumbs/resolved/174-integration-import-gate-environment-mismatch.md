---
number: "174"
title: "Integration gate import resolution runs in wrong Python environment — fails on project dependencies"
severity: high
status: resolved
kind: bug
author: gr032-post-mortem
date: "2026-05-16"
tags: [stage-8, gate, integration, CLASS-008, dep-v1-121]
related: ["CLASS-008", "121", "151", "170", "171"]
---

## Symptom

`evaluate_integration()` consistently fails the `integration_import` gate on assembled trees that import project-level dependencies (e.g. `cryptography`, `pydantic`, `requests`). The integrator produces valid JSON with correct Python source; the import loop in `gate.py:1137-1172` raises `ModuleNotFoundError`.

## Evidence

- GR-030 (0/2 integration locked), GR-031 (1/3), GR-032 (0/2): all `integration_import` failures.
- Workspace `.venv-gate` has `cryptography>=42.0` installed; direct reproduction with gate-venv python succeeds.
- Reproduction with factory `.venv/bin/python` fails with `ModuleNotFoundError: No module named 'cryptography'`.
- Gate process log shows `gate_failed gate=integration_import` but no module-level error detail because the exception is swallowed into the diagnostics list.

## Root cause

`evaluate_integration` uses **two different Python executables** for its three gates:

1. **Import resolution** (lines 1137-1172): runs **in-process** inside the gate process, using `sys.executable` (the factory's own venv), which lacks project dependencies.
2. **mypy** (lines 1184-1210): runs as a **subprocess** with `python_executable` (the gate venv), which *has* project dependencies.
3. **pytest** (lines 1212-1239): runs as a **subprocess** with `python_executable` (the gate venv).

When the assembled tree imports a project dependency, gate 1 fails while gates 2 and 3 would have passed.

## Classification

This is **CLASS-008 instance #11** — gate execution environment mismatch. Same shape as BC-121 (gate process used project venv instead of gate venv for tooling), but this time the in-process import loop is the culprit, not a subprocess invocation.

## Proposed fix

**Option A (subprocess import gate)** — run import resolution as a single subprocess under `python_executable` (the gate venv). A small helper script receives the assembled tree JSON path, attempts to import every `.py` file, and returns structured output (list of failures or empty list for success).

**Option B (site-packages injection)** — prepend the gate venv's site-packages directory to `sys.path` before the in-process import loop, then restore it in a `finally` block.

**Recommended: Option A.**

Option B is a 3-line change but violates the principle that the gate process's own environment should not be coupled to the project-under-test. Injecting project site-packages into `sys.path` creates a new failure surface:
- Project deps could shadow factory deps (e.g. an old `packaging` version).
- Mutable `sys.path` is not cleaned up correctly on exception, affecting downstream gate evaluations in the same process.
- It makes the gate's behavior dependent on the global state of a long-running process.

Option A costs one subprocess per integration item (integration items are 2-3 per run; overhead is negligible) and provides clean isolation. It also makes the import gate consistent with the mypy and pytest gates, which already use subprocesses.

## Gate budget impact

None. This fixes an existing gate (`integration_import`) whose implementation was incomplete, not adding a new gate. The budget is about *new* deterministic gates, not fixing broken ones.

## Fix

Implemented in `gate.py` (BC-174 session):

- Replaced in-process `importlib.util` loop with a subprocess invocation under `python_executable` (the gate venv).
- The subprocess receives a self-contained `-c` script that performs the same import loop, outputs a JSON array of errors, and exits 0 on success.
- The parent process parses the JSON output and returns the same `GateResult` shape as before.
- `py_files` is now computed once before Gate 1 and reused by Gates 2 (mypy) and 3 (pytest).

## Acceptance criteria

- [x] Integration import resolution uses the gate venv python (same executable as mypy/pytest gates).
- [ ] GR-033 or later shows `integration_import` passing on assembled trees with project dependencies.
- [x] No `sys.path` mutation in the gate process.
- [x] Failure diagnostics include the actual import exception traceback.
