---
number: "075"
title: "Inner gate loop — pre-submission mypy+ruff validation for implementer role"
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

1. **`pre_gate.py`** (new): `pre_gate_implementation()` runs mypy (with dependency `.pyi` files) and ruff (check + format) against the implementer's artifact before submitting to substrate. Returns `PreGateResult` with pass/fail status for each check and combined diagnostics.

2. **`runner.py`**: Added `_inner_gate_loop()` in `process_work_item`. After the channel produces an artifact for the implementer role, runs pre-gate checks. If any fail, re-derives context with diagnostics as `prior_failures`, re-invokes the channel, and tries again. Loops up to `FactoryConfig.inner_gate_retries` times (default 2).

3. **`FactoryConfig`**: Added `inner_gate_retries: int = 2` field. Configurable per golden-run. Set to 2 for GR010.

The inner loop only runs mypy and ruff (fast, deterministic checks). It does not run pytest because pytest requires the full workspace setup (test files, dependencies) that the inner loop doesn't have. Pytest failures still go through the outer gate_process loop.

## Results

GR010 showed the inner gate loop catching a ruff line-too-long error and retrying (visible in logs as `inner_gate_failed_retry`). The loop correctly doesn't fix runtime logic bugs (the remaining `cannot_proceed` on FR-03 is `leaf=None` in pytest — a bug mypy/ruff can't catch). Tests: 5 new tests in `test_pre_gate.py`.