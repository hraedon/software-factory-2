# Golden Run 023 — Phase 4 Broken-Impl Fixture, K2-Only

**Date:** 2026-05-13
**Config:** `golden-run-023-config.yaml` (project `sf2_golden_023_broken`)
**Channel:** opencode (kimi-k2p6-turbo via Fireworks), K2-only
**Fixture:** `tests/fixtures/broken-impl` (1 spec: `wi_broken_calc.md`)
**Workflow version:** 4 (phase4.yaml)

## Purpose

Validate Phase 4 pipeline (all 5 stages) on the synthetic `broken-impl` fixture using K2 only. Validate inner-gate telemetry end-to-end: `SubmitPayload.inner_gate_attempts` carrying inner gate retry history, and telemetry reporter extracting it into the exit-criteria summary.

## Results Summary

| Stage | Total | Locked | Cannot proceed | Lock rate |
|---|---|---|---|---|
| interface_spec | 1 | 1 | 0 | 100% |
| test_suite | 1 | 1 | 0 | 100% |
| implementation | 1 | 1 | 0 | 100% |
| review | 1 | 1 | 0 | 100% |
| jury | 1 | 1 | 0 | 100% |
| **Total** | **5** | **5** | **0** | **100%** |

**Wall clock:** ~60 min.
**Zero stuck items.**

## Key validations

1. **Inner gate telemetry:** `telemetry.py` correctly extracted inner gate attempts from `SubmitPayload.inner_gate_attempts` in regista submit events. Inner gate first-pass rate line appeared in the exit-criteria report.
2. **All 5 roles exercised:** interface_architect → test_author → implementer → cross_family_reviewer → frontier_judge.
3. **Review and jury gates:** `evaluate_review()` and `evaluate_jury()` both passed on the first attempt.

## Telemetry

| Role | Channel | Family | Gate | Items | 1st-Att | Overall | MeanDur |
|---|---|---|---|---|---|---|---|
| interface_architect | opencode | fireworks | interface_spec | 1 | 100% | 100% | — |
| test_author | opencode | fireworks | test_suite | 1 | 100% | 100% | — |
| implementer | opencode | fireworks | implementation | 1 | 100% | 100% | — |
| cross_family_reviewer | opencode | fireworks | cross_family_review | 1 | 100% | 100% | — |
| frontier_judge | jury_aggregate | multi | jury_quorum | 1 | 100% | 100% | — |

## Issues and observations

- Inner gate data was present in regista events and correctly parsed by telemetry. The two-source-of-truth problem (BC-133) is resolved.

## Next steps

1. Run multi-family jury with `jury_quorum=2` and mixed families.
2. Validate `jury_disagree` path with a synthetic or naturally-occurring disagreement.

## Comparison

| Metric | GR-022 | GR-023 | Delta |
|---|---|---|---|
| Fixture | cert-watch-mini (3 specs) | broken-impl (1 spec) | smaller |
| Family | K2-only | K2-only | — |
| Lock rate | 100% (15/15) | 100% (5/5) | — |
| Wall clock | ~50 min | ~60 min | similar (fixture size effect) |

## Conclusion

Phase 4 pipeline successfully processes single-spec fixtures end-to-end with inner gate telemetry fully wired. BC-133 validated.
