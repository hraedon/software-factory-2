---
number: "175"
title: "integration_mypy fails with 'Source file found twice' when assembled tree contains __init__.py"
severity: high
status: proposed
kind: bug
author: gr035-post-mortem
date: "2026-05-16"
tags: [stage-8, gate, integration, mypy, integrator, CLASS-008]
related: ["174", "170", "171"]
---

## Symptom

`integration_mypy` fails before reporting any real type errors when the
integrator's `assembled_tree` includes a top-level `__init__.py`. The mypy
output is:

```
certificate_model.py: error: Source file found twice under different module
  names: "<tmp_dirname>.certificate_model" and "certificate_model"
Common resolutions include:
    a) adding `__init__.py` somewhere,
    b) using `--explicit-package-bases` or adjusting `MYPYPATH`
```

mypy bails immediately (`errors prevented further checking`), so no actionable
type diagnostics reach the integrator on retry.

## Evidence

- GR-035 attempt 4, work item `b77419a6-a914-4e3c-9f11-172fb960e306`
  (`integration_mypy` failed). Artifact preserved at
  `/tmp/sf2-golden-035/b77419a6-.../attempt-0001/artifact.json` — the
  integrator emitted `__init__.py` re-exporting names from
  `certificate_model`.
- Reproduction outside the gate: same artifact, same flags (`mypy --strict
  --no-error-summary <file list>`), `cwd=tmp_path`, `MYPYPATH=tmp_path`
  reproduces the error deterministically.
- Removing `__init__.py` from the assembled tree turns the failure into the
  *real* (separate) mypy issues (see BC-176), confirming this is the gating
  failure mode.

## Root cause

`evaluate_integration` (`gate.py:1212-1222`) invokes:

```python
subprocess.run(
    [exe, "-m", "mypy", "--strict", "--no-error-summary", *mypy_targets],
    cwd=str(tmp_path),
    env=gate_subprocess_env(MYPYPATH=str(tmp_path)),
)
```

`mypy_targets` is the list of `.py` files in the assembled tree. When the
tree contains `__init__.py`, mypy treats the directory as a package named
after its basename and resolves each listed file to `<basename>.<module>`.
But `MYPYPATH=tmp_path` also lets mypy resolve the same file as bare
`<module>`. mypy detects this collision and refuses to continue.

This is a long-standing mypy ergonomics trap that becomes structural in our
gate setup because both ingredients (file-list targets + MYPYPATH including
the file dir) are required by the current gate design.

## Why GR-034 didn't hit this

GR-034 (`cert-watch-mini`, 3 items) had a simpler assembled tree that the
integrator emitted without `__init__.py`. GR-035's larger surface and
re-export style produced one, exposing the latent bug.

## Fix options

**Option A (preferred):** Invoke mypy against the *directory* and let it
discover modules:

```python
subprocess.run(
    [exe, "-m", "mypy", "--strict", "--no-error-summary",
     "--explicit-package-bases", str(tmp_path)],
    cwd=str(tmp_path),
    env=gate_subprocess_env(MYPYPATH=str(tmp_path)),
)
```

`--explicit-package-bases` with directory targeting tells mypy "treat
`tmp_path` as a package base; modules below it have names relative to that
base." This eliminates the dual-resolution and works for trees with or
without `__init__.py`.

**Option B:** Strip `__init__.py` from the assembled tree before running
gates. Loses any re-export semantics the integrator intended; intrusive.

**Option C:** Skip `MYPYPATH` and rely on `cwd` alone. mypy `--strict` then
sometimes can't resolve internal references — worse than (A).

## Acceptance criteria

- AC-1: `integration_mypy` runs to completion on an assembled tree
  containing `__init__.py`; mypy reports the underlying type findings (if
  any) instead of bailing on the duplicate-module error.
- AC-2: Existing passing GR-034 case still passes.
- AC-3: New regression test in `tests/test_gate_integration.py` builds a
  fixture assembled tree with `__init__.py` and asserts mypy gate reaches
  the real check phase.

## Touched surface

- `src/factory/gate.py` — `evaluate_integration`, mypy invocation (~line 1213-1222).
- `tests/test_gate_integration.py` — add regression fixture.

## Related

- BC-174 — `integration_import` gate env mismatch (resolved).
- BC-176 — `mypy --strict` rejects ellipsis-body stubs in integration tree
  (separate failure mode, surfaced once this BC is fixed).
- BC-177 — pytest sys.path inheritance can shadow assembled modules.

## Resolution

Implemented in `src/factory/gate.py` (`evaluate_integration`, Gate 2) during
BC-175/176/177 bundle session. Discovered during GR-035 forensics.

**Change:** Replaced the file-list mypy invocation with a directory target
and added `--explicit-package-bases`. The `mypy_targets` file list is no
longer passed; mypy discovers modules under `tmp_path` itself:

```python
subprocess.run(
    [exe, "-m", "mypy", "--strict", "--no-error-summary",
     "--explicit-package-bases", "--allow-empty-bodies",
     str(tmp_path)],
    cwd=str(tmp_path),
    env=gate_subprocess_env(MYPYPATH=str(tmp_path)),
)
```

`--explicit-package-bases` tells mypy to resolve all modules relative to
`tmp_path`, eliminating the dual-resolution collision that occurred when
`__init__.py` was present.

**Regression tests** locked in by `tests/test_integration_gates.py`:
- `TestBC175MypySourceFileTwice::test_tree_with_init_py_reaches_real_check_phase`
- `TestBC175MypySourceFileTwice::test_tree_with_init_py_and_type_error_fails_on_real_error`

Status: `status: resolved`
