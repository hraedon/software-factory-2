---
number: "CLASS-008"
title: "Gate Subprocess Execution and Environment Handling"
severity: high
status: stabilized
kind: defect-class
author: rfc-016-backfill
date: "2026-05-15"
tags: [gate, subprocess, environment, sandbox]
related: ["059", "088", "093", "094", "099", "104", "114", "141", "142", "RFC-012"]
---

## Shape

A gate subprocess (ruff, mypy, pytest, import smoke-check) fails or misbehaves because its execution environment is wrong: wrong cwd, wrong PATH, wrong env vars, missing credentials, tool not found, or the subprocess mutates files it should not.

## Systemic cause

Gate subprocesses are invoked from multiple call sites (gate.py, pre_gate.py, runner.py) with independently constructed environments. There is no shared subprocess-execution layer that standardizes env construction, cwd, PATH, credential stripping, and size guards. Each call site re-implements subprocess invocation.

## Systemic fix

RFC-011's shared execution layer, combined with RFC-012's sandbox module (already implemented: `factory/sandbox.py`). Ensure all gate subprocess calls go through `gate_subprocess_env()` and a common subprocess runner.

## Trigger condition

≥5 instances (current: 12). Past threshold.

## Instances

| BC   | Symptom |
|------|---------|
| 059  | Gate soft-fail on missing tooling — returns passed=True |
| 088  | Inner gate retry overwrites original artifact in-place |
| 093  | Command injection in pre_gate import smoke check |
| 094  | Tests write to hardcoded /tmp paths |
| 099  | SubprocessChannel.invoke replaces entire child environment |
| 104  | Gate layer reads artifacts without size limits |
| 114  | pre_gate _run_ruff_fast mutates artifact file in-place |
| 141  | opencode run returns empty output when cwd is not a project directory |
| 142  | agent_golden_run.py launched processes from /tmp |
| 174  | Integration import gate runs in wrong Python env — fails on project deps |
| 187  | invocation_cwd=repo root causes model subprocess to write fixture artifacts into repo root |
| RFC-012 | Gate subprocess credential stripping and sandboxing |

## Status under RFC-030

**Decision: Path A — systemic fix. Implemented.**

RFC-011 `implemented` as of 2026-05-20. `factory.subprocess.run` provides the typed wrapper invariant: keyword-only `cmd`, `cwd`, `env`, `timeout_s` with no defaults. All 29 subprocess call sites in `src/factory/` migrated through the wrapper. CLASS-008 instance table is now unblocked for new entries (though the systemic fix should prevent recurrence).