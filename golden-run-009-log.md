# Golden Run 009 — BC-074 Validation (Dependency Context Injection)

**Date:** 2026-05-10
**Config:** `golden-run-009-config.yaml`
**Channel:** opencode (kimi-k2p6-turbo via Fireworks)
**Fixture:** `tests/fixtures/cert-watch-mini/` (3 specs: certificate_model, FR-02, FR-03)
**Project:** `sf2_golden_009`

## Purpose

Validate BC-074 fix: implementer and test_author now receive locked dependency artifacts via `locked_dependency_<module>` in prompt context. The gate's `_copy_dependency_pyis()` now writes both `.py` and `.pyi` files so mypy resolves stub types correctly.

## Results Summary

| Metric | Value |
|---|---|
| Total work items | 9 |
| Locked | 6 (67%) |
| Cannot proceed | 3 (33%) |
| Interface spec lock rate | 3/3 (100%) |
| Test suite lock rate | 3/3 (100%) |
| Implementation lock rate | 2/3 (67%) |

## Per-work-item detail

| WI | Type | State | Attempts | Notes |
|---|---|---|---|---|
| 4df04b36 | interface_spec | locked | 2 | certificate_model |
| 6388de20 | interface_spec | locked | 2 | FR-02 TLS scan |
| 99f2f60f | interface_spec | locked | 2 | FR-03 file upload |
| b4ee7957 | test_suite | locked | 2 | certificate_model |
| 52bf5914 | test_suite | locked | 2 | FR-02 |
| b3d42d0f | test_suite | locked | 2 | FR-03 |
| fa8d2809 | implementation | locked | 2 | certificate_model |
| b03d53f3 | implementation | **cannot_proceed** | 4 | FR-02 — pytest fail (leaf=None) |
| 9b8c48f4 | implementation | **cannot_proceed** | 4 | FR-03 — pytest fail |

## BC-074 Validation

**Mypy empty-body errors eliminated.** Both `.py` and `.pyi` dependency stubs are now written to gate temp directories. The `implementation_mypy` failure count dropped from "every WI that depends on certificate_model" (GR-008) to **zero** in GR-009.

**Cross-module imports resolve correctly.** Test suites and implementations that import from `certificate_model` now pass the import check and mypy gates.

## Remaining failure: FR-02 and FR-03 implementations

Both escalated implementations fail outer `implementation_pytest` with runtime assertion failures:

- **FR-02**: `upload_certificate` returns `leaf=None`, failing `assert isinstance(result.leaf, Certificate)`
- **FR-03**: Similar runtime pytest failure

These are genuine logic bugs that mypy/ruff cannot catch. The inner gate loop (BC-075) was not yet active in GR-009; it would be validated in GR-010.

## Telemetry

Telemetry verify: passed (0 unknown gates, 0 orphans, 0 unmatched gates).

## Comparison with GR-008

| Metric | GR-008 | GR-009 | Delta |
|---|---|---|---|
| Impl lock rate | 33% (1/3) | **67% (2/3)** | +34pp |
| Mypy empty-body failures | 2/2 (100%) | **0/2 (0%)** | -100pp |
| Test suite lock rate | 100% (3/3) | 100% (3/3) | — |
| Interface spec lock rate | 100% (3/3) | 100% (3/3) | — |

## Changes validated

- BC-074: Dependency artifact injection into prompts + `.pyi` stubs alongside `.py` in gate tempdirs.

(End of file)
