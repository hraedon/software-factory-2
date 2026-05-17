---
number: "184"
title: "interface .pyi stubs with ellipsis bodies trigger mypy 'abstract attributes' retry-exhaustion for impls"
severity: high
kind: bug
status: implemented
author: claude
date: "2026-05-17"
tags: [inner-gate, mypy, interface-architect, prompt, retry-exhaustion, phase5]
related: ["176", "183"]
---

## Symptom

In GR-036, three consecutive implementation work items (74cf8c15, 22958fa9, fa69d565)
each exhausted all three inner-gate retries on the **identical** mypy diagnostic
emitted against their dependency `.pyi`:

```
database_layer.pyi:45: error: Class database_layer.SqliteCertificateRepository
  has abstract attributes "add", "delete", "get_by_id", "list_all",
  "list_expiring_within", "update_expiry"  [misc]
database_layer.pyi:45: note: If it is meant to be abstract, add 'abc.ABCMeta'
  as an explicit metaclass
```

Per-item evidence in `.factory/logs/gr036/runner.log`:
- 74cf8c15: 22:52→23:27 (retry 0/1/2 then `inner_gate_exhausted_retries`)
- 22958fa9: 23:31→23:37 (same)
- fa69d565: 23:42→ (same)

In all three, `ruff_passed=True`, `pytest_passed=True`, `imports_symbols_passed=True`;
only `mypy_passed=False`. Retry feedback was insufficient — the model produced a
fix that did not address the underlying issue (the offending `.pyi` is a locked
upstream artifact the implementer cannot edit) and the cycle repeated.

## Root cause (verified)

`copy_dependency_pyis` in `pre_gate.py` writes the dependency `.pyi` content
verbatim as BOTH `<module>.pyi` (for mypy type-checking) and `<module>.py`
(so the implementation can be imported during pytest). When mypy type-checks
`interface.py` (the impl), it loads `database_layer.py` via `MYPYPATH` and
processes it as a regular Python module. A `.py` file with `...` bodies for
methods that return non-`None` triggers `[empty-body]` errors (mypy 2.x) or
`[misc]` "has abstract attributes" (mypy 1.x) against that dependency `.py`.

The implementer cannot edit the locked dependency `.pyi`, so every retry
produces a cosmetically-different impl that still fails the same mypy gate.

Note: `--allow-empty-bodies` was added to `.pyi`-targeting mypy invocations in
BC-176, but that flag only silences stub files (`.pyi`) — NOT regular `.py`
files processed as dependencies. The shadow `.py` written by `copy_dependency_pyis`
is a regular file, so BC-176 was incomplete for this failure mode.

The breadcrumb's hypothesis that the error fires because the architect omits
`ABCMeta` is partially correct for mypy 1.x. In mypy 2.x the identical root
cause (shadow `.py` with `...` bodies) manifests as `[empty-body]`.

## Severity rationale

High. GR-036 wasted three independent impl work items (~30 min of model time
each) on the same untriable failure. Any future GR whose spec produces a
`.pyi` with concrete classes containing multiple method stubs will hit the
same trap. Combined with BC-183 (false-positive import feedback), retry
exhaustion is currently a systemic failure mode for the inner gate, not a
random unlucky case.

## Fix chosen

**Variant of Option A applied at `copy_dependency_pyis` (not at the
interface_architect artifact level).** The interface_architect continues to
emit `.pyi` stubs with `...` bodies — the artifact format is unchanged.
The fix is in the copy step that creates the Python-importable shadow:

1. **`pre_gate.py` — new `_stub_content_to_py()` helper**: AST-parses the stub
   content and replaces every ellipsis-only function/method body with
   `raise NotImplementedError`. The `.py` shadow written by `copy_dependency_pyis`
   now has valid Python bodies, so mypy no longer fires `[empty-body]` on it.

2. **`copy_dependency_pyis` calls `_stub_content_to_py(content)`** when writing
   the `.py` shadow. The `.pyi` shadow is still written with the original content.

3. **`--allow-empty-bodies` added to both `_run_mypy_fast` (pre_gate.py) and
   `_run_mypy` (gate.py)**: suppresses `[empty-body]` on the `interface.pyi`
   stub itself (equivalent of BC-176 for the worktree state).

Option B was rejected: `--allow-empty-bodies` does not apply to `.py` files and
`--disable-error-code=misc` is too broad.
Option C was rejected: model compliance is not guaranteed; mechanical fix is
safer.

Why not modify `interface_architect.md`? The problem is in the copy layer, not
the architect's output — changing the prompt would not fix existing locked stubs
in flight, and future stubs in transit before the prompt change would still hit
the same gate failure.

## Acceptance criteria

- AC-1: a deterministic test reproduces the GR-036 failure: a `.pyi` with
  concrete class + multi-method `...` bodies + an impl that subclasses it
  must NOT emit `[misc]` "has abstract attributes" through the inner mypy
  gate.
- AC-2: existing inner-mypy tests still pass; genuine abstract-class misuse
  (impl forgets to override a real `@abstractmethod`) still surfaces an error.
- AC-3: if Option C is chosen, interface_architect prompt updated and a
  golden-fixture run produces `.pyi` files that pass inner mypy without
  retry exhaustion.

## Out of scope

- The wider question of whether `.pyi` is the right interface artifact format
  at all — defer to whatever RFC covers artifact format choice.
- Retry-feedback quality improvements (separate concern, may want its own BC).

## Touched surface (actual)

- `src/factory/pre_gate.py`:
  - added `_stub_content_to_py()` AST helper
  - `copy_dependency_pyis` uses it for the `.py` shadow
  - `_run_mypy_fast` gains `--allow-empty-bodies`
- `src/factory/gate.py`:
  - `_run_mypy` gains `--allow-empty-bodies`
- `tests/test_pre_gate.py`:
  - `TestBC184AbstractAttributesRetryTrap` — AC-1 and AC-2 regression tests
  - `TestStubContentToPy` — unit tests for the helper
  - `TestCopyDependencyPyis.test_py_shadow_has_raise_not_ellipsis` — content assertion
  - Two pre-existing `test_fails_on_mypy_error` / `test_mypy_failure_skips_pytest`
    updated: `pass` body → `return 42` (genuine type error not suppressed by
    `--allow-empty-bodies`)
- `tests/test_gate_implementation_subprocess.py`:
  - `TestBC184AbstractAttributesRetryTrap.test_ac1_dep_pyi_ellipsis_bodies_do_not_fail_impl_mypy`

Test results: 955 passed, 13 skipped, 0 failed.
