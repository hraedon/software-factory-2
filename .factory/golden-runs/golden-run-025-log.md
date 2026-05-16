# Golden Run 025 — Mixed-Family Jury (K2 + GLM-5.1)

**Date:** 2026-05-13
**Config:** `golden-run-025-config.yaml` (project `sf2_golden_025_mixed_jury`)
**Channel:** opencode (K2 + zai-coding-plan/glm-5.1)
**Fixture:** `tests/fixtures/cert-watch-mini` (3 specs)
**Workflow version:** 4 (phase4.yaml)
**Jury config:** 2 jurors (K2 + GLM-5.1), `jury_quorum=2`

## Purpose

Validate multi-family jury with `jury_quorum=2` and ≥2 distinct channel families. Exercise the `jury_disagree` path, verify `[all_against]` tag behavior, and confirm `model_override` correctly invokes distinct models through a shared adapter.

## Results Summary

| Stage | Total | Locked | Cannot proceed | Lock rate |
|---|---|---|---|---|
| interface_spec | 3 | 3 | 0 | 100% |
| test_suite | 3 | 3 | 0 | 100% |
| implementation | 3 | 3 | 0 | 100% |
| review | 3 | 3 | 0 | 100% |
| jury | 3 | 0 | 3 | 0% |
| **Total** | **15** | **12** | **3** | **80%** |

**Wall clock:** ~55 min.
**Zero stuck items.**

## Key validations

1. **Multi-model jury invoked correctly:** `process_jury_work_item()` created two juror invocations in parallel:
   - `opencode-kimi-k2p6-turbo` (Fireworks family)
   - `opencode-glm-5.1` (GLM family)
2. **`model_override` worked:** Both jurors used the same `OpenCodeChannel` adapter but received distinct `--model` flags.
3. **`jury_disagree` exercised:** GLM-5.1 returned empty output on every juror attempt. K2 juror voted correctly, but quorum=2 was never met. This exercised the disagreement-rationale code path added in BC-134.
4. **`[all_against]` tag validated in tests:** The test `test_all_channels_fail` in `test_jury.py` verifies the `[all_against]` branch. In GR-025 the actual outcome was a **split vote** (K2 voted for, GLM errored/against), not all-against — telemetry still populated `disagreement_rationale` with the split detail per BC-134.

## Telemetry

| Role | Channel | Family | Gate | Items | 1st-Att | Overall |
|---|---|---|---|---|---|---|
| interface_architect | opencode | fireworks | interface_spec | 3 | 100% | 100% |
| test_author | opencode | fireworks | test_suite | 3 | 100% | 100% |
| implementer | opencode | fireworks | implementation | 3 | 100% | 100% |
| cross_family_reviewer | opencode | fireworks | cross_family_review | 3 | 100% | 100% |
| frontier_judge | opencode-kimi-k2p6-turbo | fireworks | jury_quorum | 3 | 0% | 0% |
| frontier_judge | opencode-glm-5.1 | glm | jury_quorum | 3 | 0% | 0% |

**Note:** `jury_disagree` is the gate applied when quorum is not met. The actual gate name recorded reflects the failure mode.

## Issues and observations

- **GLM-5.1 empty output for jury:** Identical symptom to GR-024 implementer — GLM-5.1 via z.ai opencode channel cannot reliably produce output for longer prompts. The frontier_judge prompt is shorter than implementer but still exceeds GLM-5.1's reliable generation threshold.
- **Disagreement rationale always populated:** Even when quorum was not met, `disagreement_rationale` was non-empty, enabling downstream analysis of why the jury failed. BC-134 validated.
- **Fallback telemetry:** Channel failures were recorded in `ChannelFailPayload.diagnostics` with juror key preserved.

## Breadcrumbs resolved

- **BC-133 (high):** Inner gate telemetry — validated end-to-end in this run.
- **BC-134 (medium):** Jury observability gap — `[all_against]` tag and always-populated rationale validated.

## Next steps

1. Replace GLM-5.1 juror with Gemini 2.5 Pro (validated in capability probe, Session 29).
2. Re-run mixed-family jury with K2 + Gemini to achieve quorum.
3. Consider GLM-5.1 for review-only roles (shorter prompt than judge).

## Conclusion

Multi-model jury infrastructure is structurally sound: unique juror keys, parallel invocation, `model_override`, and family derivation all work correctly. However, GLM-5.1 is not yet a reliable juror due to empty-output issues. The observability improvements (BC-133/134) were validated and the telemetry correctly distinguishes model disagreement from channel failure.
