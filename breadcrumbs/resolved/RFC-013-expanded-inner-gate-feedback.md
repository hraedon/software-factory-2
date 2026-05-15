---
number: "RFC-013"
title: "Expanded inner-gate feedback for implementer retries — richer failure signal without infra overhead"
severity: medium
status: resolved
kind: design
author: glm-5-1
date: "2026-05-11"
tags: [runner, gate, inner-gate, implementer, rfc, phase3]
related: ["075", "RFC-009"]
---

## Problem

When the inner gate loop rejects an implementer artifact, the retry prompt includes the gate name and a pass/fail status, but limited diagnostic detail. The implementer model must guess what went wrong from the gate label alone (e.g., "inner_pytest failed"). This forces the model to regenerate broadly rather than targeting the specific failure.

In GR-014, the 2 escalation failures were an invalid dataclass definition and an ImportError — both would have been immediately identifiable from `pytest --tb=short` output. The inner gate *has* this information (it runs the tools), but doesn't currently pass it back to the model.

## Current behavior

`_inner_gate_loop` in `runner.py`:
1. Runs `pre_gate_implementation()` (mypy → ruff → pytest, short-circuit)
2. On failure, records `PreGateResult(gate_name=..., passed=False, output=...)`
3. Retries by re-invoking the channel with the original prompt + failure context
4. The failure context includes the gate name but the diagnostic output is logged, not fed back to the model

## Proposed enhancement

### 1. Capture tool output in PreGateResult (minimal change)

`PreGateResult` already carries an `output` field. Ensure the actual stderr/stdout from mypy, ruff, and pytest is captured and stored in this field for each failing gate.

### 2. Inject failure diagnostics into retry prompt

When the inner gate loop retries, include the diagnostic output from the failing gate in the prompt context. Structure it as:

```
## Previous attempt failed

Gate: inner_pytest
Output:
<last ~50 lines of pytest --tb=short output>

Please fix the issues above.
```

Truncate output to a configurable bound (default: 2000 chars) to avoid context bloat. This is the "richer failure signal" — the model sees *what* failed, not just *that* something failed.

### 3. Gate-specific output tailoring

Different gates produce useful output at different verbosity levels:

| Gate | Useful output | Suggested command |
|---|---|---|
| inner_mypy | Error lines with column numbers | `mypy --no-error-summary` (last 30 lines) |
| inner_ruff | Violation listing | `ruff check --output-format=concise` (last 30 lines) |
| inner_pytest | Traceback + failure summary | `pytest --tb=short -q` (last 50 lines) |

The inner gate already runs these exact commands. The change is capturing and forwarding their output rather than discarding it.

### 4. Incremental failure history

For multi-retry scenarios (inner_gate_retries > 1), accumulate failure summaries:

- Attempt 1: inner_mypy failed — include mypy output
- Attempt 2: inner_pytest failed — include pytest output + note that mypy now passes

This gives the model a trajectory ("type errors fixed, now test failures") rather than isolated snapshots.

## Why not Docker / full development environment

RFC-009 proposes giving the implementer interactive tool-use access during generation — the agent runs code, sees output, iterates. That's the right long-term answer but requires channel-level tool-use support that not all adapters provide (opencode supports it; claude code supports it; gemini CLI may not).

This RFC is the lightweight version: use the diagnostic output the inner gate *already produces* and feed it back to the model. No new infrastructure, no channel capability requirements, works across all adapters. Expected impact: inner gate retry success rate improves because the model gets actionable signal instead of blind retry.

## Phase placement

Phase 3. The inner gate loop exists, `PreGateResult` carries output, the change is wiring existing information into the retry prompt. No new subprocess calls, no new infrastructure.

## Scope

- `src/factory/runner.py` — `_inner_gate_loop` retry prompt construction
- `src/factory/pre_gate.py` — ensure output capture for all three gates
- `src/factory/config.py` — optional `inner_gate_max_feedback_chars` (default 2000)
- Tests for retry prompt content

## What this doesn't do

- Give the agent tool-use access during generation (that's RFC-009)
- Provide a development environment with dependency isolation (that's Phase 5)
- Address the interface-first rigidity (that's a spec-level design choice, not a tooling gap)

## Resolution

Implemented: inner gate loop captures PreGateResult.output (gate stdout/stderr), truncates to configurable `inner_gate_max_feedback_chars` (default 2000), accumulates FailureEntry history across retries, and injects prior failures into retry prompt via `render_prompt()`. See `src/factory/runner.py` lines 700-740 and `src/factory/config.py` line 113.
