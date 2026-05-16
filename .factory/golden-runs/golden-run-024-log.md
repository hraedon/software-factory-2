# Golden Run 024 — GLM-5.1 Isolated Role Validation

**Date:** 2026-05-13
**Config:** `golden-run-024-config.yaml` (project `sf2_golden_024_glm`)
**Channel:** opencode (zai-coding-plan/glm-5.1 via z.ai)
**Fixture:** `tests/fixtures/cert-watch-mini` (3 specs)
**Workflow version:** 4 (phase4.yaml)

## Purpose

Evaluate GLM-5.1 as the sole model for all five pipeline roles. Isolated role validation removes confounding from other models and measures GLM's standalone reliability on a small fixture before considering it for load-bearing roles or jury duty.

## Results Summary

| Stage | Total | Locked | Cannot proceed | Lock rate |
|---|---|---|---|---|
| interface_spec | 3 | 3 | 0 | 100% |
| test_suite | 3 | 3 | 0 | 100% |
| implementation | 3 | 0 | 0 | 0% |
| review | — | — | — | — |
| jury | — | — | — | — |
| **Total (incomplete)** | **9 of 15** | **6** | **—** | **—** |

**Wall clock:** ~70 min.
**Run incomplete:** implementer stage blocked all downstream items.

## Per-role findings

### interface_architect — PASSED (3/3 locked)
GLM-5.1 produced valid `.pyi` interface specs for all 3 specs. Intermittent empty-output retries (3–4 attempts each) but eventually succeeded.

### test_author — PASSED (3/3 locked)
All 3 test suites produced pytest-collectable tests. Similar intermittent retry pattern as interface_architect.

### implementer — FAILED (0/3 locked, run incomplete)
Consistent empty output on every implementer invocation (6/6 attempts observed). The implementer prompt includes interface spec + test suite + dependencies + prior failures — significantly longer than upstream role prompts.
- Workspace: `/tmp/sf2-golden-024/`
- All `raw_stdout.txt` files: 0 bytes
- Direct CLI test with same prompt structure succeeds, suggesting provider-side rate-limit, context-window, or chat-bias tuning.

## Telemetry

| Role | Channel | Family | Gate | Items | 1st-Att | Overall |
|---|---|---|---|---|---|---|
| interface_architect | opencode | glm | interface_spec | 3 | ~30% | 100% |
| test_author | opencode | glm | test_suite | 3 | ~30% | 100% |
| implementer | opencode | glm | implementation | 3 | 0% | 0% |

## Issues opened

- **BC-135 (medium):** glm-5.1 returns empty output for implementer role — model reliability issue. Filed during this run; resolved in commit `ff6b7ce` (empty-output retry + stderr capture), but GLM-5.1 remains unsuitable for implementer due to sustained failure rate.

## Next steps

1. Relegate GLM-5.1 to review/judge roles only (shorter prompts, no code generation).
2. Use K2 or Gemini Pro for implementer on multi-family runs.
3. If multi-family jury requires GLM, restrict its juror prompts to the short frontier_judge template.

## Conclusion

GLM-5.1 is viable for interface_architect and test_author with retries, but **not viable for implementer** due to persistent empty-output failures on long prompts. This is a model reliability issue, not a pipeline bug.
