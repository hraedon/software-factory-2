---
number: "170"
title: "Pre-gate ruff mutates integrator JSON artifact — invalidates integration_import gate"
severity: high
status: resolved
kind: bug
author: opencode
date: "2026-05-15"
tags: [artifact, immutability, integrator, pre-gate, stage-8, CLASS-021]
related: ["154", "CLASS-021"]
---

## Symptom

In GR-030, both integration work items (0/2 locked) failed with `integration_import` gate reporting "Artifact is not valid JSON". The model had emitted valid JSON with double-quoted strings, but the artifact on disk contained single-quoted Python strings.

## Root cause

Causal chain (5 steps, all confirmed with preserved workspace evidence):

1. `_artifact_extension_for_role` (`subprocess_channel.py:48-52`) returned `.py` for every role except `interface_architect`. So the integrator's JSON output was written as `artifact.py`.

2. `_INNER_GATE_ROLES` (`runner.py:69-77`) included `ROLE_INTEGRATOR`, so the inner-gate loop ran on it.

3. The inner-gate path fell through to `pre_gate_implementation` (`runner.py:621`), which called `_run_ruff_fast` → `_apply_ruff_fix` (`pre_gate.py:691`).

4. Ruff treated the `.py` file as Python. `ruff format` normalized quote style — converting `"..."` JSON strings into `'...'` Python strings.

5. The artifact was now invalid JSON. `evaluate_integration` (`gate.py:1071`) called `json.loads()` and failed with `integration_import`.

Evidence preserved in `.factory/gr030-workspace-backup/4549d299…/attempt-0001/`:
- `.artifact.py.orig` — pre-ruff content, valid JSON with `"` strings.
- `artifact.py` — post-ruff content, with `'` strings. Not valid JSON.

The `.orig` backup is created by `_apply_ruff_fix` at `pre_gate.py:695`, so its existence is proof ruff modified the file.

Ruff "succeeded" silently. The pytest inner gate also passed trivially because no `test_suite_path` is provided for the integrator role (`pre_gate.py:788-789`). The failure surfaced only at the outer gate's `json.loads()`.

## Fix

Two-part surgical fix:

1. **Extension**: `_artifact_extension_for_role` now returns `.json` for `ROLE_INTEGRATOR` and `ROLE_OUTCOME_VERIFIER`. Artifacts are saved as `artifact.json` instead of `artifact.py`.

2. **Pre-gate routing**: `_run_pre_gate` (`runner.py`) now dispatches integrator to `pre_gate_integrator()` and outcome_verifier to `pre_gate_outcome_verifier()` — JSON-shape validators that check parseability and required keys, without invoking ruff/mypy/pytest. These roles no longer fall through to `pre_gate_implementation`.

## Lesson

Pre-gates must not mutate non-Python artifacts. The ruff fixer is designed for `.py` files and silently corrupts JSON by normalizing quote style. New roles with non-Python artifact shapes need dedicated pre-gate validators that understand the artifact format, not the Python-centric default path.
