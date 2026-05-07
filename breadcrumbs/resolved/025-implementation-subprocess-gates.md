---
number: "025"
title: "evaluate_implementation missing subprocess gates"
severity: high
status: implemented
kind: bug
author: session-8
date: "2026-05-07"
tags: [gate, stage-5, runner]
resolution: added-import-check-mypy-pytest-ruff-gates
---

## Background

`evaluate_implementation` only checked file_exists, not_empty, and syntax. The `DiagnosticKind` entries `IMPL_MYPY`, `IMPL_PYTEST`, `IMPL_LINT`, `IMPL_IMPORT` existed in the router dispatch table but were unreachable because the gate never produced them. Per the Phase 2 plan Wave 1, these gates are required for meaningful implementation verification.

## Fix applied (2026-05-07)

Added four gates to `evaluate_implementation` in `gate.py`:

1. **Import check** (`_check_impl_imports`): AST-based, catches `import pytest`/`import conftest` in implementations. Produces `diagnostic_kind="impl_import"`.
2. **mypy** (`_run_mypy`): Subprocess `mypy --strict` against the locked interface stub. Skips if mypy not installed. Produces `diagnostic_kind="impl_mypy"`.
3. **pytest** (`_run_pytest`): Runs test suite against implementation with `PYTHONPATH` set. Skips if pytest not installed. Produces `diagnostic_kind="impl_pytest"`.
4. **ruff** (`_run_ruff`): Runs `ruff check` on the implementation. Skips if ruff not installed. Produces `diagnostic_kind="impl_lint"`.

Gates run in order: syntax → import → mypy → pytest → ruff. Short-circuits on first failure. Tests in `test_gate_implementation_subprocess.py`.
