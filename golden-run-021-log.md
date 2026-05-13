# Golden Run 021 — BC-131 Validation (Runtime Import Resolution Feedback)

**Date:** 2026-05-13
**Config:** `golden-run-021-config.yaml`
**Channel:** opencode (kimi-k2p6-turbo via Fireworks), K2-only
**Fixture:** `tests/fixtures/cert-watch/` (8 specs, full DAG)
**Project:** `sf2_golden_021`
**Workflow version:** 3

## Purpose

Validate BC-131: `_parse_import_failure()` classifies `ModuleNotFoundError`/`ImportError` as dotted_submodule, wrong_module_name, or other_traceback; suggests closest module name via difflib; generates actionable feedback under 500 chars for model retry context.

## Results Summary

| Stage | Total | Locked | Cannot proceed | Lock rate |
|---|---|---|---|---|
| interface_spec | 8 | 8 | 0 | 100% |
| test_suite | 8 | 8 | 0 | 100% |
| implementation | 8 | 8 | 0 | 100% |
| **Total** | **24** | **24** | **0** | **100%** |

**Wall clock:** ~40 min (03:48 – 04:28 UTC).
**Zero stuck items. Zero ruff failures.**

## Inner gate first-attempt analysis

| Metric | Value |
|---|---|
| Inner gate first-attempt pass (retry=0) | 20/27 (74%) |
| Inner gate first-attempt fail | 7/27 (26%) |
| wrong_module_name failures recovered on retry=1 | 5/5 (100%) |

## BC-131 validation — PASSED

5 `wrong_module_name` import failures were caught by `_parse_import_failure()` and fed back as structured `import_feedback_kind` in the retry prompt. **All 5 recovered on retry=1.**

Example log line:
```
inner_gate_failed_retry diagnostics=[...] import_feedback_kind=wrong_module_name ... retry=0
inner_gate_passed retry=1
```

## First-attempt failure modes

| Gate label | Count | Share | Role |
|---|---|---|---|
| `inner_import_check` (wrong_module_name) | 5 | 71% | interface_architect |
| `inner_import_check` (other) | 1 | 14% | interface_architect |
| `inner_mypy` | 1 | 14% | implementer |

## Telemetry verification

```
verify_passed: True
unknown_gate_name_count: 0
unknown_gate_name_rate: 0.0000
orphan_submit_count: 0
unmatched_gate_count: 0
confounding_warning_count: 0
```

## Comparison with GR-020

| Metric | GR-020 | GR-021 | Delta |
|---|---|---|---|
| Lock rate | 100% (24/24) | 100% (24/24) | — |
| Inner gate first-attempt | 77% (20/26) | 74% (20/27) | -3pp |
| Mean attempts to lock | 1.08 | ~1.08 | — |
| wrong_module_name recovery | N/A (pre-BC-131) | **100% (5/5)** | New |

## Changes validated

- BC-131: `_parse_import_failure()` in `pre_gate.py` with difflib-based module name suggestion
- `import_feedback` field in `PreGateResult` and `PromptContext`
- `import_feedback_kind` in `inner_gate_failed_retry` structlog events
- Composite gate names added to `deterministic_gates` set in telemetry
- `_inner_gate_label()` helper extracted in `runner.py`

## Phase 3 exit criteria — ALL MET

All Phase 3 exit criteria remain met. BC-131 is a quality improvement, not a threshold fix.

(End of file)
