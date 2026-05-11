---
number: "RFC-011"
title: "Unified gate evaluation — extract shared subprocess execution layer to eliminate drift between outer and inner gate implementations"
severity: medium
status: deferred
kind: design
author: deepseek-v4-pro (adversarial review — Session 20)
date: "2026-05-11"
tags: [gate, runner, stage-5, refactor]
related: ["082", "079", "059"]
phase_needed: "Phase 3 (multi-channel gates)"
---

## Problem

The outer gate (`gate.py`) and inner gate (`pre_gate.py`) contain near-duplicate subprocess execution for mypy, ruff, and pytest with systematic divergence in:
- Tool path resolution (ruff: `shutil.which` vs `python -m ruff`)
- Tool-failure behavior (BC-059 fix applied to outer only; inner still silent-passes)
- Exception handling (outer: explicit failure; inner: bare `except: passed=True`)
- Diagnostic truncation strategy (outer: first 10 lines; inner: last 3 or first 10)
- Ruff auto-format step (outer runs `ruff format`; inner doesn't)

BC-082 tracks the active manifestations. This RFC proposes the structural fix.

## Proposed design

Extract a shared gate evaluation runner (`gate_runner.py` or similar) that provides:

```
class GateRunner:
    def run_mypy(artifact_path, stub_path, dep_paths, ...) -> GateSubprocessResult
    def run_ruff(artifact_path, auto_fix=True, auto_format=True, ...) -> GateSubprocessResult
    def run_pytest(artifact_path, test_path, dep_paths, ...) -> GateSubprocessResult
    def run_pytest_collect(test_path, ...) -> GateSubprocessResult
```

Key properties:
1. Single source of truth for tool discovery (ruff path, mypy module, pytest module)
2. Uniform tool-not-found handling (always `passed=False, tool_not_found`)
3. Uniform exception propagation (never `passed=True` on error)
4. Configurable auto-format behavior (inner gate may want tighter timeout, less formatting)
5. Uniform diagnostic shapes

Both `gate.py` and `pre_gate.py` delegate all subprocess execution to `GateRunner`. The gate modules retain only the AST-level checks (syntax, stub, structural_semantics, assertions, imports).

Refactoring order:
1. Fix BC-079 first (urgent: inner gate silent-pass on tool failure)
2. Extract GateRunner with inner gate as primary consumer
3. Migrate outer gate to GateRunner
4. Add tests verifying behavioral equivalence between inner and outer for the same inputs

## Why deferred

This is a refactor — it doesn't fix a correctness bug that's blocking Phase 2. BC-079 and BC-082 track the concrete manifestations. The refactor should happen before Phase 3 (multi-channel gates), since adding more channel-specific gate logic on top of divergent tool handling is a recipe for drift acceleration.

## Relationship to v1 pattern

v1 had the same pattern: gate logic accreted across files with independent fixes applied to each copy. The "string constant gravity" lesson (v1 BC-383) generalizes to "subprocess invocation gravity" — two copies of the same subprocess call will diverge given enough time.
