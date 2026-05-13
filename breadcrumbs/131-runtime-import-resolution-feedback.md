---
number: "131"
title: "Runtime import resolution feedback quality — dotted submodule and module-not-found errors"
severity: high
status: proposed
kind: improvement
author: glm-5.1
date: "2026-05-13"
tags: [gate, runner, interface_architect, dep-resolution, pre-gate, rfc-015-followup, stage-2]
related: ["RFC-015", "126"]
---

## Problem

RFC-015 (implemented, validated by GR-020) eliminated the "wrong symbol name" class of import failures. The AST-only `validate_artifact_imports` gate catches `from X import Y` where `Y` is not in `X`'s export map. GR-020 shows **zero** of those failures.

But `interface_architect` with dependencies still fails first-attempt at 46% (GR-019+020 aggregate, 6/7 failures in GR-020). The remaining class is **runtime import resolution**: the model constructs an import path that `importlib` cannot resolve at `_run_import_check` time, even though the symbol itself is valid.

From GR-020 runner logs:

```
inner_gate_failed_retry  diagnostics=['Traceback (most recent call last):', ...]  
  imports_symbols_passed=True mypy_passed=True pytest_passed=True retry=0 ruff_passed=True
```

The `imports_symbols_passed=True` confirms the symbol is in the manifest. The failure is the **runtime** `_run_import_check` — a `ModuleNotFoundError` or `ImportError` that the model cannot diagnose from the raw `Traceback` output (which points at a temp path like `/tmp/sf2_import_xxx/artifact.py`).

## What the model is doing wrong

Two patterns observed in GR-020:

1. **Dotted submodule imports** — `from cryptography.hazmat.primitives import serialization` instead of `from cryptography import hazmat` or flattening to the top-level module. RFC-015 explicitly scoped out submodule resolution. The model doesn't know this boundary exists.

2. **Wrong module path inference** — The model guesses the module name from the stub filename or the prompt section heading, not from the actual module name used in the dependency's own imports. Example: writing `from cert_model import Certificate` when the locked stub's module is `certificate_model`.

## Proposed fix

**Not a gate addition.** The gate already catches this (`_run_import_check` in `pre_gate_interface_spec`). The fix is **feedback quality** — when `_run_import_check` fails, parse the exception and emit structured diagnostics the model can act on.

### Implementation

In `_run_import_check` (or its consumer in the inner-gate loop), when the subprocess import fails:

1. **Parse the `ModuleNotFoundError` / `ImportError` message** to extract:
   - The failing import statement (from the artifact AST, by line number if available)
   - The module name that could not be resolved
   - Whether it is a dotted path (`a.b.c`)

2. **Emit structured feedback**:

   ```
   Import resolution failed at artifact.py:4: from cryptography.hazmat.primitives import serialization
   
   Dotted submodule imports (from a.b import c) are not supported by the inner gate.
   Available flat modules: cryptography, certificate_model, database_layer, cert_chain_library
   
   If you need a symbol from a submodule, import from the top-level module and access it 
   by attribute: import cryptography; cryptography.hazmat.primitives.serialization.load_pem(...)
   ```

3. **Also handle the "wrong module name" case**:

   ```
   Import resolution failed at artifact.py:4: from cert_model import Certificate
   
   Module 'cert_model' not found. Available modules: certificate_model, database_layer
   Did you mean: certificate_model?
   ```

### Scope boundary

**In scope:**
- Parse `_run_import_check` `Traceback` output into actionable strings
- Detect dotted submodule pattern (`from a.b import c`) and explain the restriction
- Suggest closest module name match (Levenshtein or simple prefix match)
- Inject feedback into the retry prompt alongside existing diagnostics

**Explicitly out of scope (guardrails against v1 scope creep):**
- No actual submodule resolution logic (no `sys.path` manipulation, no `importlib` deep traversal)
- No `__all__` tracking
- No re-export handling
- No `TYPE_CHECKING` block resolution
- No reverse "unused dependency" check
- No auto-fix of bad imports (the gate reports; the model fixes)
- No manifest file format change

## Phase placement

Phase 3 (current). Pure runner/prompt change — no new gate stage, no new substrate transition, no new channel adapter.

## Validation criteria

- GR-021 (next clean run) shows `interface_architect` with dependencies first-attempt pass rate ≥ 70% (up from 46%)
- Zero `Traceback` import failures where `imports_symbols_passed=True` (currently 6 in GR-020)
- Feedback character count < 500 chars per failure (model context budget)
- No new breadcrumbs for submodule resolution edge cases (scope discipline)

## Why not extend RFC-015?

RFC-015's scope was locked in principal review with explicit boundaries:

> "No submodule import resolution (from a.b import c)"  
> "No re-export tracking"  
> "No attribute access checking"

This breadcrumb is a **feedback-layer** fix, not a gate-layer extension. It teaches the model the boundary RFC-015 drew, rather than crossing the boundary. That distinction is what keeps v2 from recreating v1's scope creep.

## PR shape

One PR:
1. `src/factory/pre_gate.py` — enhance `_run_import_check` return value to include parsed failure kind + suggestions
2. `src/factory/runner.py` — wire structured feedback into retry prompt context
3. `tests/test_import_feedback.py` — test cases for dotted-submodule detection, module-name suggestion, feedback character budget
4. `breadcrumbs/131-*.md` — flip `status: proposed` to `status: implemented` on merge
