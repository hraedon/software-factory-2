---
number: "208"
title: "mutation_gate.py _run_pytest duplicates pre_gate and gate pytest logic"
severity: high
status: in_progress
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

## Partial fix (Session 53)

1. **Telemetry corruption fixed**: `_run_pytest` in mutation_gate.py now returns `GATE_NAME_MUTATION_SPOT_CHECK` instead of `GATE_NAME_IMPLEMENTATION_PYTEST`. This ensures mutation test failures are correctly categorized in telemetry.
2. **Gate name check fixed**: `evaluate_mutation_spot_check` now checks for `GATE_NAME_MUTATION_SPOT_CHECK` instead of `GATE_NAME_INNER_PYTEST` when filtering ineligible results.
3. **"pytest not installed" check added**: mutation_gate's `_run_pytest` now handles "No module named pytest" with `tool_not_found` diagnostic_kind.
4. **Diagnostic truncation aligned**: Changed from `lines[:10]` to `(lines + err_lines)[-3:]` matching pre_gate's strategy.
5. **Real interface stub handling**: Added logic to copy the real interface .pyi stub when `interface_pyi_path` is provided, instead of always creating a dummy from implementation content.
6. **Unused imports removed**: `GATE_NAME_IMPLEMENTATION_PYTEST` and `GATE_NAME_INNER_PYTEST` no longer imported.
7. **Gate name filter bug fixed**: `evaluate_mutation_spot_check` had a gate name check that included `GATE_NAME_MUTATION_SPOT_CHECK`, which caused ALL pytest results to be filtered as ineligible (the check was meant to filter inner-gate failures only). Fixed to check only `GATE_NAME_INNER_MYPY`.

## Remaining

The three-way duplication still exists. Full unification would extract a shared pytest runner in `gate/_subprocess.py` that all callers delegate to. The mutation_gate variant is intentionally different (uses real interface .pyi, not dummy), so full unification requires the shared function to accept an optional `interface_pyi_path` parameter.
