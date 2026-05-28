# Golden Run 022 — Phase 4 First Golden Run

**Date:** 2026-05-13
**Config:** `golden-run-022-config.yaml` (project `sf2_golden_022d`)
**Channel:** opencode (kimi-k2p6-turbo via Fireworks), K2-only
**Fixture:** `tests/fixtures/cert-watch-mini` (3 specs)
**Workflow version:** 4 (phase4.yaml)

## Purpose

Validate the Phase 4 pipeline end-to-end: interface_spec → test_suite → implementation → review → jury, with all five roles (interface_architect, test_author, implementer, cross_family_reviewer, frontier_judge) exercised on real model output.

## Results Summary

| Stage | Total | Locked | Cannot proceed | Lock rate |
|---|---|---|---|---|
| interface_spec | 3 | 3 | 0 | 100% |
| test_suite | 3 | 3 | 0 | 100% |
| implementation | 3 | 3 | 0 | 100% |
| review | 3 | 3 | 0 | 100% |
| jury | 3 | 3 | 0 | 100% |
| **Total** | **15** | **15** | **0** | **100%** |

**Wall clock:** ~50 min (19:44 – 20:44 UTC).
**Zero stuck items. Zero ruff failures.**

## Key validation: Phase 4 pipeline shape

- **Scheduler created all downstream work items correctly:**
  - 3 interface_specs → 3 test_suites
  - 3 test_suites → 3 implementations
  - 3 implementations → 3 reviews
  - 3 reviews → 3 juries
- **Runner handled review + jury work items transparently:**
  - `cross_family_reviewer` role: 3 items, 100% first-attempt pass
  - `frontier_judge` role: 3 items, jury_quorum=1, 100% pass (single-family jury)
- **Gate processed review + jury artifacts:**
  - `evaluate_review()` and `evaluate_jury()` both passed
- **Telemetry verify:** passed (0 unknown gates, 0 orphans, 0 unmatched)

## Phase 4 prompt template validation

The `cross_family_reviewer.md` and `frontier_judge.md` prompt templates produced parseable JSON on first attempt for all 6 invocations (3 reviews + 3 juries). No markdown wrapping or trailing comma issues observed.

## Telemetry

| Role | Channel | Family | Gate | Items | 1st-Att | Overall | MeanDur |
|---|---|---|---|---|---|---|---|
| cross_family_reviewer | opencode | fireworks | cross_family_review | 3 | 100% | 100% | 16.3s |
| frontier_judge | jury_aggregate | multi | jury_quorum | 3 | 100% | 100% | — |
| implementer | opencode | fireworks | implementation | 3 | 100% | 100% | 76.2s |
| interface_architect | opencode | fireworks | interface_spec | 3 | 100% | 100% | 58.0s |
| test_author | opencode | fireworks | test_suite | 3 | 100% | 100% | 67.0s |

## Issues fixed during this session

1. **`populate_work_items.py` Phase 4 inference:** Added `phase4` to `--workflow` choices and version 4 mapping.
2. **`FactoryConfig.from_yaml()` stage_topology parsing:** Added YAML parsing for `StageHandoff` objects (was silently dropping the key, causing default Phase 2 topology).
3. **`workflows/phase4.yaml` custom fields:** Added `dependency_refs`, `ac_ids`, `spec_section`, `module_name` to `review` and `jury` work item types (regista rejected unknown fields).

## What was NOT validated

- **Multi-family jury racing:** All jury channels were K2 (same family). A true multi-family jury requires at least 2 distinct families in the config.
- **Review gate failure routing:** All reviews passed on first attempt; the `review_fail → new` retry path was not exercised.
- **Jury disagreement/quorum-not-met:** All juries met quorum; the `jury_disagree` gate and disagreement rationale were not exercised.

## Next steps

1. **Multi-family jury GR:** Re-run with `jury_quorum=2` and at least two distinct channel families (e.g., K2 + Claude or K2 + GLM).
2. **Review gate edge cases:** May need synthetic test to exercise review rejection + retry.
3. **Telemetry reporter** currently labels the output as "Phase 3 Exit Criteria Summary" — should be updated to "Phase 4" once exit criteria are defined.

## Comparison with GR-021 (Phase 3)

| Metric | GR-021 | GR-022 | Delta |
|---|---|---|---|
| Fixture | cert-watch full (8 specs) | cert-watch-mini (3 specs) | smaller |
| Workflow | phase3 (3 stages) | phase4 (5 stages) | +review +jury |
| Total work items | 24 | 15 | +2 stages per spec |
| Lock rate | 100% (24/24) | 100% (15/15) | — |
| Wall clock | ~40 min | ~50 min | +10 min (review+jury) |
| First-attempt pass | 74% inner gate | 100% outer gate | different metric |

## Conclusion

**Phase 4 pipeline skeleton is functional.** All 15 work items locked, all new roles (cross_family_reviewer, frontier_judge) produced parseable output, and the scheduler correctly propagated 4 handoffs per spec. The run did not exercise failure modes (review rejection, jury disagreement, multi-family racing) — those are the next validation targets.
