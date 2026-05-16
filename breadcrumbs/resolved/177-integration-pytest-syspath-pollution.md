---
number: "177"
title: "integration_pytest subprocess inherits parent PYTHONPATH; stray /tmp modules can shadow assembled tree"
severity: medium
status: proposed
kind: bug
author: gr035-post-mortem
date: "2026-05-16"
tags: [stage-8, gate, integration, pytest, hermetic-execution, CLASS-008]
related: ["175", "176", "174"]
---

## Symptom

`integration_pytest` can fail collection with `ImportError` on a symbol that
*exists* in the assembled tree but does not exist in a same-named module
elsewhere on the Python search path. Observed during local repro of the
GR-035 attempt-4 artifact:

```
ImportError: cannot import name 'parse_pem_certificate' from
'certificate_model' (/tmp/certificate_model.py)
```

The integrator's `certificate_model` (in the workspace tmp dir) *does*
export `parse_pem_certificate`. A stray `/tmp/certificate_model.py` left
over from an unrelated earlier run was on `sys.path` ahead of the workspace
and shadowed it.

## Evidence

- Reproduced locally with the GR-035 artifact and a stray
  `/tmp/certificate_model.py` present: pytest collection fails.
- Removing the stray file: all 5 integration tests pass.
- Whether the GR-035 gate process itself hit the same shadow is not
  confirmable from `gate.log` (stdout/stderr from the gate subprocess is
  not captured at the level needed); but the conditions for it to happen
  exist by design.

## Root cause

`evaluate_integration` (`gate.py:1245-1251`) invokes pytest like this:

```python
subprocess.run(
    [exe, "-m", "pytest", str(test_path), "-x", "--tb=short", "-q"],
    cwd=str(tmp_path),
    env=gate_subprocess_env(PYTHONPATH=str(tmp_path)),
)
```

Two compounding risks:

1. **`gate_subprocess_env` may not strip the parent's `PYTHONPATH`** — if
   the gate process itself has `PYTHONPATH` set (e.g. via developer
   ergonomics, CI config, or a venv activation that prepends paths), that
   value can survive into the child process and prepend extra directories
   ahead of `tmp_path`.

2. **`pytest` and CPython both implicitly add directories to `sys.path`**
   that aren't controlled by `PYTHONPATH`:
   - CPython prepends the script's directory to `sys.path[0]`.
   - pytest's rootdir + conftest discovery can insert ancestor directories.
   - On some configurations, `/tmp` (the parent of the workspace) ends up
     ahead of `tmp_path` if the test file is referenced by absolute path.

Either of these can cause a same-named module elsewhere on the system to
shadow the assembled tree.

This violates the Phase-5 hermetic-execution intent: a gate subprocess
should only see the assembled tree (plus the gate venv's site-packages).

## Fix

Three defensive changes in `evaluate_integration` (and parallel changes in
`_run_mypy` to the extent they share the same surface):

1. **Build the pytest env with explicit allow-list, not inheritance.**
   `gate_subprocess_env` (look up the helper in
   `src/factory/gate.py`) should accept a flag like
   `inherit_pythonpath=False` and, when set, explicitly *clear*
   `PYTHONPATH` before adding the workspace dir. Default to the safe
   behavior.

2. **Add `--rootdir <tmp_path>` and `-p no:cacheprovider`** to the pytest
   arg list. The first pins rootdir to the workspace (preventing pytest
   from walking up to `/tmp` looking for `conftest.py`). The second
   avoids cache pollution between gate runs.

3. **Sandbox isolation** (longer-term): consider running the gate
   subprocess with `tmp_path` as a chroot-like working dir via
   `subprocess.run(..., env={"PYTHONPATH": str(tmp_path), "PATH": ...,
   "PYTHONDONTWRITEBYTECODE": "1"}, ...)` rather than passing through
   `os.environ`. This is consistent with RFC-005 sandbox direction.

## Acceptance criteria

- AC-1: `integration_pytest` subprocess no longer inherits the parent's
  `PYTHONPATH`. Verified by a regression test that sets a misleading
  `PYTHONPATH` in the parent before invoking the gate and confirms it does
  not leak.
- AC-2: A stray module of the same name in `/tmp` does not shadow the
  workspace module. Regression test creates `/tmp/<modname>.py` with wrong
  exports and asserts the gate still resolves the workspace copy.
- AC-3: `--rootdir` and `-p no:cacheprovider` are present in the gate's
  pytest command.

## Touched surface

- `src/factory/gate.py` — `evaluate_integration` pytest invocation
  (~line 1245-1251); `gate_subprocess_env` helper.
- `tests/test_gate_integration.py` — regression tests.

## Severity rationale

Medium rather than high: hard to trigger in clean CI; reproducible in
developer environments and in long-running golden-run boxes where `/tmp`
accumulates artifacts. Still load-bearing for hermetic-execution
guarantees, and cheap to fix.

## Related

- BC-175, BC-176 — same gate, separate failure modes; should land as a
  bundle since the regression tests share a fixture.
- BC-174 — `integration_import` env mismatch (resolved); same gate, same
  family of bugs.
- RFC-005 — sandbox/hermetic-execution direction.

## Resolution

Implemented in the BC-175/176/177 bundle session. Discovered during GR-035 forensics.

**Changes:**

1. `src/factory/sandbox.py` — `gate_subprocess_env` gains an
   `inherit_pythonpath: bool = False` parameter. When False (the default),
   both `PYTHONPATH` and `MYPYPATH` are stripped from the base environment
   before overrides are applied. All existing callers pass explicit values
   for these keys via `**overrides`, so the default flip is safe — no
   caller depends on inheritance.

2. `src/factory/gate.py` — integration pytest invocation (`evaluate_integration`
   Gate 3) updated with `--rootdir={tmp_path}` and `-p no:cacheprovider`.

3. All callers of `gate_subprocess_env` audited — none required
   `inherit_pythonpath=True`.

**Regression tests** locked in by `tests/test_integration_gates.py`:
- `TestBC177HermeticPytest::test_misleading_parent_pythonpath_does_not_leak`
  — sets a misleading `PYTHONPATH` via monkeypatch; gate still passes.
- `TestBC177HermeticPytest::test_stray_tmp_module_does_not_shadow_workspace`
  — writes a stray `/tmp/<modname>.py` with wrong exports; workspace copy wins.

Status: `status: resolved`
