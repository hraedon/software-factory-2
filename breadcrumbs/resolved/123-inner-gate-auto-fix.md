---
number: "123"
title: "Inner gate auto-fix: copy ruff-corrected artifacts back instead of retrying"
severity: medium
status: resolved
kind: improvement
author: opencode-session-eval
date: "2026-05-12"
tags: [inner-gate, ruff, retry, throughput, phase-3]
related: ["075", "122"]
---

## Problem

The inner gate retry loop (`_inner_gate_loop` in runner.py) calls `_run_ruff_fast` which copies the artifact to a temp dir, runs `ruff check --fix`, then `ruff format`, then `ruff check`. If the final check passes, the function returns `passed=True` — but the *original artifact file* is unchanged. The model then receives the ruff error output as a prior failure and regenerates the entire artifact.

This is wasteful for auto-fixable issues (import sorting, unused imports, blank lines, formatting) that ruff can fix deterministically. The model doesn't need to regenerate; the fixed temp-file version is already valid.

## Root cause

`pre_gate.py::_run_ruff_fast` is designed as a *diagnostic* function: it checks if the artifact passes ruff and returns diagnostics. It does not mutate the original artifact.

## Proposed fix

Option A (minimal): If `_run_ruff_fast` passes after auto-fix, copy the temp-file version back to the original artifact path. Return `passed=True` with empty diagnostics so the inner gate loop does not trigger a retry.

Option B (moderate): Separate "auto-fixable" from "unfixable" ruff errors. Run `ruff check --fix` first. If it fixes the file, consider the gate passed without retry. Only retry on unfixable errors (syntax, undefined names).

Option C (architectural): Add a `GateStrategy` enum: `AUTO_FIX` vs `REJECT`. The ruff gate is AUTO_FIX: apply fixes and accept. The mypy/pytest gates are REJECT: fail and retry.

## Trade-offs

- **Pro:** Dramatically reduces retry count for ruff-shaped failures. In GR-015, every interface_spec failed ruff on first attempt — this would make them pass immediately.
- **Con:** The model never learns to generate ruff-clean code. Telemetry still shows 0% first-attempt pass rate even though the pipeline runs faster. This is acceptable if we treat first-attempt rate as a throughput metric, not a model-quality metric.
- **Con:** Risk of accepting a "fixed" artifact that changes semantics (ruff --fix is safe for most rules, but edge cases exist).

## Affected files

- `src/factory/pre_gate.py` — `_run_ruff_fast`
- `src/factory/runner.py` — `_inner_gate_loop` (optional: skip retry if gate label is inner_ruff)

## Phase placement

Phase 3. This is a throughput optimization that requires no model or prompt changes. It complements BC-122 (prompt checklists) by handling the cases the model still misses.

## Related

BC-075 (inner gate loop) created the retry mechanism. This breadcrumb refines it.
