# Golden Run 015 — Phase 3 Multi-Channel Dispatch, K2-Only (BC-121 fix)

**Date:** 2026-05-12
**Config:** `golden-run-015-config.yaml`
**Channel:** opencode (kimi-k2p6-turbo via Fireworks), K2-only binding
**Fixture:** `tests/fixtures/cert-watch/` (8 specs, full DAG)
**Project:** `sf2_golden_015`
**Workflow version:** 3 (phase3.yaml)

## Results Summary

| Stage | Total | Locked | Cannot proceed | Lock rate |
|---|---|---|---|---|
| interface_spec | 8 | 8 | 0 | 100% |
| test_suite | 8 | 8 | 0 | 100% |
| implementation | 8 | 8 | 0 | 100% |
| **Total** | **24** | **24** | **0** | **100%** |

**Wall clock:** ~60 min (22:10 – 23:10 UTC).

## Telemetry verify

Passed (0 unknown gates, 0 orphans, 0 unmatched gates).

## Key finding: 0% first-attempt pass rate

Every work item required inner-gate retry=1 (or retry=2) to pass. This is a **prompt-shaped problem**, not a model-shaped one — the prompts do not teach the model to self-check before returning output.

## Critical regression discovered: BC-121

During initial GR-015 execution, outer gate failed every test_suite and implementation with "pytest not installed" / "mypy not installed" / "ruff not installed".

**Root cause:** BC-115 moved gate tooling into a separate `.venv-gate`, but `gate_process.py` and `runner.py` still called `ensure_project_venv()` which returns the project-venv python (now gate-tool-free after `_clean_stale_project_venv` runs).

**Fix committed during session:**
- `ensure_gate_venv()` made public; installs both `_GATE_TOOLS` and project `requirements.txt`
- `gate_process.py` and `runner.py` both use `ensure_gate_venv()` for gate operations
- GR-015 re-run with fixed code: **100% lock rate, 24/24 items**

## Changes since GR-014

- Phase 3 workflow (phase3.yaml) with 3-stage pipeline
- K2-only binding per validated channel policy
- BC-121 fix: gate/runner use gate venv

## Breadcrumbs opened

- BC-122: Prompt pre-flight checklist to improve first-attempt pass rate (high)
- BC-123: Inner gate auto-fix: copy ruff-corrected artifacts back instead of retrying (medium)
- BC-124: Selective ruff rule set for model output — relax non-critical rules (medium)

(End of file)
