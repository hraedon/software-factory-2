# Golden Run 010 — BC-075 Validation (Inner Gate Loop)

**Date:** 2026-05-10
**Config:** `golden-run-010-config.yaml`
**Channel:** opencode (kimi-k2p6-turbo via Fireworks)
**Fixture:** `tests/fixtures/cert-watch-mini/` (3 specs: certificate_model, FR-02, FR-03)
**Project:** `sf2_golden_010`
**Inner gate retries:** 2 (new config field)

## Purpose

Validate BC-075: pre-submission validation loop for implementer role. New `pre_gate.py` runs mypy+ruff against the artifact before submitting; runner's `_inner_gate_loop` retries up to `inner_gate_retries` with diagnostics fed back as `prior_failures`.

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
| 1ff54aba | interface_spec | locked | 2 | certificate_model |
| aa5f745c | interface_spec | locked | 2 | FR-02 TLS scan |
| a6e17e64 | interface_spec | locked | 2 | FR-03 file upload |
| c048d425 | test_suite | locked | 2 | certificate_model |
| 9945af42 | test_suite | locked | 4 | FR-02 — inner gate caught ruff errors |
| 53840002 | test_suite | locked | 2 | FR-03 |
| d129da71 | implementation | locked | 2 | certificate_model |
| e02efb97 | implementation | **cannot_proceed** | 4 | FR-02 — pytest fail |
| 3a9c132a | implementation | **cannot_proceed** | 4 | FR-03 — pytest fail |

## Inner Gate Analysis

| Item | Gate | Retry 0 | Retry 1 | Retry 2 | Outcome |
|------|------|---------|---------|---------|---------|
| 9945af42 (test_suite) | inner_ruff | E501 Line too long | RUF059 unused var | — | Exhausted, submitted anyway, outer gate passed retry 1 |

The inner gate caught ruff errors on one work item (9945af42, FR-02 test_suite):
- **Retry 0**: E501 Line too long (114 > 100)
- **Retry 1**: RUF059 Unpacked variable `oid_tag` is never used
- Exhausted max_retries=2, submitted anyway. Outer gate then passed on a subsequent attempt.

## BC-075 Validation

Inner gate loop is functioning:
- Catches ruff/format issues before submission
- Feeds diagnostics back into retry prompt context
- Saves model's raw output as `.<name>.orig` before writing fixed version

## Remaining failures

Same as GR-009: FR-02 and FR-03 implementations fail `implementation_pytest` with runtime assertion errors (leaf=None, isinstance checks). These are model quality issues, not pipeline bugs.

## Telemetry

Telemetry verify: passed (0 unknown gates, 0 orphans, 0 unmatched gates).

## Comparison

| Metric | GR-009 | GR-010 | Delta |
|---|---|---|---|
| Impl lock rate | 67% (2/3) | 67% (2/3) | — |
| Inner gate active | No | **Yes** | New |
| Ruff failures pre-submission | N/A | 1 WI caught | Validated |

## Changes validated

- BC-075: Inner gate loop with mypy+ruff pre-submission validation.

(End of file)
