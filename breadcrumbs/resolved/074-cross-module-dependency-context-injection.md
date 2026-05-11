---
number: "074"
title: "Cross-module dependency types invisible to implementer and test_author — models fabricate stubs causing mypy empty-body failures"
severity: high
status: implemented
kind: bug
author: glm-5.1
date: "2026-05-10"
tags: [runner, context, gate, stage-4, stage-3]
related: ["072"]
---

## Problem

GR006a, GR007, and GR008 all showed implementation lock rates of 33% on the cert-watch-mini fixture. Root cause: `derive_implementer_context()` and `derive_test_author_context()` did not resolve `CUSTOM_FIELD_DEPENDENCY_REFS` or inject dependency `.pyi` artifacts into `extra_artifacts`. The implementer couldn't see the types it depended on, so it fabricated local stubs with `...` bodies, which mypy's `empty-body` check rejected.

Meanwhile, the gate (`gate_process.py`) correctly resolved and copied dependency `.pyi` files into temp directories via `_copy_dependency_pyis()` — so the model was blind to the types during creation, but mypy saw them during evaluation.

Additionally, `_copy_dependency_pyis()` wrote dependency content as `.py` files only. When mypy ran in a temp directory with `interface.pyi` alongside `interface.py`, it would use the `.pyi` for the primary interface but treat dependency modules as `.py` files with `...` bodies, triggering `empty-body` errors.

## Impact

- Implementation lock rate: 33% on cross-module fixtures (GR006a, GR007, GR008)
- Consistent failure pattern: mypy `empty-body` on `certificate_model.py:22, 27`
- Test suites locked at 100% because they don't deeply exercise dependency types

## Resolution

Three changes:

1. **`context.py`**: Added `_resolve_dependency_contents()` helper and `_extract_module_name_from_spec()`. Both `derive_test_author_context()` and `derive_implementer_context()` now resolve `CUSTOM_FIELD_DEPENDENCY_REFS` from the work item's custom_fields, read each dependency's artifact, and inject it as `locked_dependency_<module_name>` in `extra_artifacts`. The module name is derived from the spec section header (same logic as `gate_process.py`).

2. **`gate.py`**: `_copy_dependency_pyis()` now writes both `module.py` (for pytest imports) and `module.pyi` (for mypy type resolution). When mypy sees a `.pyi` alongside a `.py`, it uses the `.pyi` for type checking — and `...` stubs are valid in `.pyi` files.

3. **`implementer.md` and `test_author.md`**: Added `locked_dependency_<module>` to "What you receive" and rule #6: "Use dependency types, do not recreate them."

## Results

GR009 (same fixture, same channel) improved from 33% to 67% implementation lock rate. The mypy `empty-body` error was eliminated. Tests: 3 new tests in `test_context.py` verifying dependency injection.