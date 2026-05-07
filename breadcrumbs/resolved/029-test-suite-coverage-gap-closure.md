---
number: "029"
title: Test suite coverage gap closure — runner unit, IO failure, config malformed, prompt rendering, substrate coupling
severity: medium
status: implemented
kind: improvement
author: opencode
Date: "2026-05-07"
tags: [runner, gate, config, workspace, telemetry, stage-0]
related: ["020", "014", "019"]
---

## Problem

Test suite analysis (2026-05-07 session) identified eight coverage and maintainability gaps:

1. `_handle_invoke_failure` in runner.py untested at unit level (timeout vs. generic vs. `cannot_proceed`)
2. `process_work_item` resume path only tested at workspace layer, not runner layer
3. `render_prompt` and `derive_context` missing-work-item edge cases untested
4. `FactoryConfig.from_yaml` missing malformed-input tests (bad YAML, wrong types)
5. `test_workspace.py` and `test_runner_idempotency.py` duplicated `_make_manifest` helper
6. Workspace `write_artifact` / `quarantine_attempt` IO failure modes untested
7. Substrate private-API imports (`substrate._types`, `substrate.testing`) had no early-failure smoke test
8. `pytest-cov` not configured; no coverage threshold or reporting

## Resolution

- **test_runner_unit.py** (5 tests): direct `process_work_item()` unit tests for timeout, generic channel_fail, cannot_proceed, resume from valid prior attempt, resume ignores tampered artifact
- **test_context.py** expanded: 6 `render_prompt` tests (empty fields, glossary, failures, extra artifacts, prompt template inclusion, spec section ordering) + missing-work-item `ValueError` test
- **test_config.py** expanded: 4 malformed-input tests (invalid YAML raises, roles dict raises TypeError, worker_roles/gate_roles strings coerced to tuple)
- **test_workspace_io_failure.py** (5 tests): `mkdir` PermissionError, `write_bytes` OSError, `os.replace` OSError, SHA-256 known hashes
- **test_substrate_private_api_coupling.py** (3 tests): import smoke tests for `ActorMetadata`, `InMemorySubstrate`, `drop_project_schema`
- **Shared helper**: extracted `make_manifest` to `tests/_helpers.py` to eliminate duplication
- **pyproject.toml**: added `pytest-cov>=5.0` to dev deps
- **Golden-run cleanup**: removed placeholder `TestGoldenRunPending` empty assertions

## Files touched

- `src/factory/config.py` — stricter type checking in `from_yaml` (dict guard for roles, string coercion for role lists)
- `tests/_helpers.py` — new shared helper
- `tests/test_runner_unit.py` — new
- `tests/test_workspace_io_failure.py` — new
- `tests/test_substrate_private_api_coupling.py` — new
- `tests/test_config.py`, `tests/test_context.py`, `tests/test_golden_run.py`, `tests/test_runner_idempotency.py`, `tests/test_workspace.py` — modified
- `pyproject.toml` — added pytest-cov to dev deps

## Exit criterion

All tests pass (214 passed, 1 skipped) with zero lint errors on all changed files.
