---
number: "208"
title: "mutation_gate.py _run_pytest duplicates pre_gate and gate pytest logic"
severity: high
status: resolved
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

## Fix

Unified three-way pytest duplication into a single canonical `_run_pytest` in `gate/_subprocess.py`:

1. **`gate/_subprocess.py:_run_pytest`** extended with superset parameters:
   - `interface_pyi_path: Path | None = None` — real .pyi stub for mutation testing
   - `implementation_name: str | None = None` — custom filename for impl copy
   - `gate_name: str = GATE_NAME_IMPLEMENTATION_PYTEST` — caller-controlled GateResult label
   - `timeout` default changed from hardcoded `300` to `GateTimeouts.pytest_timeout`
   - Diagnostic truncation changed from `[:10]` to `[-3:]` (show tail, not head)
   - Interface handling: always creates `interface.py` from impl (for importability), then overlays `interface.pyi` if real stub provided

2. **`mutation_gate.py`**: removed 70-line local `_run_pytest`; now imports from `gate._subprocess` and passes `gate_name=GATE_NAME_MUTATION_SPOT_CHECK`. Removed unused `tempfile`, `sandbox`, `subprocess` imports.

3. **`pre_gate.py:_run_pytest_fast`**: replaced 57-line implementation with 18-line wrapper calling `gate._subprocess._run_pytest` (lazy import to avoid circular dependency with `copy_dependency_pyis`). Returns dict for backward compatibility. Removed unused `TEMPFILE_PREFIX_PYTEST`, `ARTIFACT_FILENAME_INTERFACE` imports.

**Net reduction**: ~110 lines of duplicated code eliminated.

### Why this isn't the previous fix recurring

Sessions 52–53 fixed individual symptoms (telemetry corruption, missing checks, truncation alignment) without addressing the root cause: three near-identical implementations that must stay synchronized. This fix establishes the invariant: **one canonical `_run_pytest` with a `gate_name` parameter; no caller reimplements pytest subprocess logic**. The `gate_name` parameter makes the function caller-configurable without requiring copy-paste.
