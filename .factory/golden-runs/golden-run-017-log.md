# Golden Run 017 — INCOMPLETE (GLM Implementer Binding)

**Date:** 2026-05-12
**Config:** `golden-run-017-config.yaml`
**Channel binding:** interface_architect→K2, test_author→K2, implementer→GLM-5.1
**Fixture:** `tests/fixtures/cert-watch/` (8 specs, full DAG)
**Project:** `sf2_golden_017`
**Workflow version:** 3
**Status:** **INCOMPLETE / ABORTED**

## Purpose

Compare model-family capability per role: GLM-5.1 as implementer vs K2 implementer baseline.

## Results

| Stage | Total | Locked | Cannot proceed | Stuck |
|---|---|---|---|---|
| interface_spec | 8 | 7 | 0 | 1 in_progress |
| test_suite | 8 | 3 | 0 | 5 in_progress |
| implementation | 3 | 0 | 0 | 3 stuck |
| **Total** | **19** | **10** | **0** | **9 incomplete** |

**Nanny timed out at 60 min.**

## GLM implementer assessment: NOT VIABLE

- 7/8 interface_specs locked (K2, normal behavior)
- 3/8 test_suites locked (K2, normal behavior)
- **1 implementation stuck at attempt 16** with repeated channel failures:
  - "Could not extract artifact from opencode output"
  - "Empty output from opencode"

**Assessment:** GLM-5.1 via zai-coding-plan/opencode is **not viable for implementer role** on the cert-watch workload. Smoke tests (simple prompts) passed, but real implementation prompts exceed its reliable generation capacity. Likely long-context degradation or provider-side chat-bias tuning.

## Conclusion

Run aborted at nanny timeout. GLM implementer binding rejected. Default config switched back to K2-only for implementer.

(End of file)
