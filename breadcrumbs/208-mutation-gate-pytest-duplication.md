---
number: "208"
title: "mutation_gate.py _run_pytest duplicates pre_gate and gate pytest logic"
severity: high
status: proposed
kind: improvement
author: adversarial-review
date: "2026-05-25"
tags: [gate, CLASS-005, rfc-027, mutation]
related: ["CLASS-005"]
---

## Problem

Three near-identical pytest subprocess functions exist across the codebase:

| Function | File | Lines |
|---|---|---|
| `_run_pytest` | `gate/_subprocess.py` | 166–231 |
| `_run_pytest_fast` | `pre_gate.py` | 1086–1142 |
| `_run_pytest` | `mutation_gate.py` | 52–103 |

The mutation_gate copy diverges from the other two in several ways:

- No `dependency_spec_paths` support — `copy_dependency_pyis` is called with only pyi paths
- No "pytest not installed" check (line 1128 in pre_gate, line 208 in gate/_subprocess)
- Different diagnostic truncation: mutation_gate takes `lines[:10]` while pre_gate takes `lines[-3:]`
- Uses `GATE_NAME_IMPLEMENTATION_PYTEST` for its gate name instead of a mutation-specific gate name

Additionally, `mutation_gate.evaluate_mutation_spot_check` had a hardcoded `timeout: int = 300` default that bypassed `GateTimeouts.pytest_timeout`. This was fixed in Session 52.

## Proposed fix

Extract a shared pytest runner into `gate/_subprocess.py` that all three callers use, with the same diagnostic truncation strategy, dependency handling, and timeout source. Alternatively, have `mutation_gate._run_pytest` delegate to `gate._subprocess._run_pytest` (the outer gate version) since it already handles all the edge cases.
