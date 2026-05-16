---
model: fireworks-ai/accounts/fireworks/routers/kimi-k2p6-turbo
datetime: 2026-05-16T03:30 UTC
project: software-factory-2
---

# Session Reflection — 2026-05-16

**Work summary:** Executed GR-032 (Phase 5 golden run with Claude+Gemini+K2 multi-family combo on cert-watch-mini). During post-run forensics, discovered BC-174: the `integration_import` gate was running import resolution in-process using the factory's own venv (lacking project deps like `cryptography`) instead of the gate venv. Filed BC-174 as CLASS-008 instance #11, then fixed it by replacing the in-process `importlib.util` loop with a subprocess invocation under `python_executable`. Updated GR-032 log with corrected root cause. 947 tests pass, ruff clean.

---

## On the project

The software-factory v2 pipeline is architecturally sound but still has environmental blind spots. The gate layer has three different execution contexts:
1. **In-process** (the gate process itself, running under `.venv/bin/python`)
2. **Subprocess under gate venv** (mypy, pytest, import checks after this fix)
3. **Subprocess under model channel** (opencode, claude, gemini CLI)

BC-174 reveals that these contexts were not consciously managed — the original integration import gate just used `sys.path` + `importlib.util` in-process because it was convenient, not because it was correct. The mypy and pytest gates already used subprocesses under the gate venv; import resolution should have been consistent from day one.

The project is now at 947 tests and 0 lint errors, which is a strong signal. But the test suite doesn't catch environmental mismatches like this because unit tests mock or control the environment. Integration tests against real workspaces would have caught BC-174 earlier.

## On the work done

**What went well:**
- The GR-032 run itself was clean — no channel failures, no stuck items, proper `cannot_proceed` escalations.
- Post-run forensics was methodical: reproduced the gate logic with both the factory venv and gate venv, isolating the root cause within ~10 minutes.
- The fix was small and principled (subprocess import check, ~40 lines) rather than a band-aid.
- The principal correctly pushed back on Option B (sys.path injection) and insisted on Option A (subprocess). That was the right call — Option B would have created a new failure surface.

**What I'm less confident about:**
- The subprocess `-c` script is a multi-line string literal inside `gate.py`. It's readable but not testable in isolation. If the import logic needs to grow (e.g. handling namespace packages, editable installs), it should be extracted to a proper module.
- The `py_files` list is now computed once and reused by all three gates, but the sorting key `(f.name != "__init__.py", str(f))` is a bit opaque. It prioritizes `__init__.py` first, which matters for import order, but this isn't documented inline.
- I didn't add a new integration test specifically for the gate-venv import scenario. The existing `test_integration_gates.py` tests still pass, but none exercise a workspace with external dependencies. A synthetic fixture that imports `cryptography` or `pydantic` in the assembled tree would catch regressions.

## On what remains

1. **GR-033 validation** — Run a new golden run with the BC-174 fix to confirm `integration_import` passes on cert-watch-mini with project dependencies. This is the highest priority.
2. **Integration stage prompt refinement** — Even with the gate fix, the integrator still needs to produce import-clean assembled trees. BC-171's worked example helped (GR-031 went from 0% to 33%), but the remaining failures in GR-031 were legitimate import/mypy issues, not environmental. The integrator prompt may still need tightening.
3. **BC-145 upstream routing exercise** — No golden run has yet triggered `REVIEW_FOUND_DEFECT` → structured feedback upstream. This may require a synthetic bad-impl fixture.
4. **Add integration gate test with external deps** — `test_integration_gates.py` should have a case that assembles a tree importing a package only present in the gate venv.

## Gaps to flag

- **`gate.py:1143-1186` (`_import_check_script`)**: The subprocess script is a string literal. If the logic needs to change, it's easy to introduce syntax errors in the string that won't be caught by `py_compile` on `gate.py`. Consider extracting to `factory/integration_import_check.py`.
- **Missing test coverage for gate-venv isolation**: `test_integration_gates.py` exercises import resolution but uses `sys.executable` (factory venv) in tests. A real regression test would need to install a package into a temp venv, assemble a tree that imports it, and verify `evaluate_integration` passes.
- **`evaluate_integration` success gate name**: `GATE_NAME_INTEGRATION` is returned on success, but the telemetry table shows it as `integration_import` for pass events because that's the gate name in `actor_metadata`. This is a minor telemetry skew that BC-151 previously fixed for the success case, but the label may still be inconsistent.
- **Gate venv without pip (uv-created)**: The gate venv at `/tmp/sf2-golden-032/.venv-gate` was created by `uv` and lacks `pip`. The `_gate_tools_hash` function queries `pip show` — this might fail or behave differently with uv-installed packages. No failure observed yet, but it's a latent issue.
