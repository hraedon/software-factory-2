# BC-137 Capability Probe — outcome_verifier

**Date:** 2026-05-15
**Role:** outcome_verifier (new Phase 5 model-mediated gate)
**Probe:** Flawed rate-limiter assembly with 6 planted defects (D1–D6)
**Methodology:** Single-attempt, no inner gate, production prompt template
**Models evaluated:** 3 Tier-A candidates

---

## Results Summary

| Model | Family | Verdict | Routing hint | Score / 12 | Status |
|---|---|---|---|---|---|
| kimi-k2.6-ollama | moonshot | fail | implementation | 12 | **PASS** |
| deepseek-v4-pro-ollama | deepseek | fail | implementation | 12 | **PASS** |
| glm-5.1-zai | zhipu | fail | implementation | 12 | **PASS** |

All three models:
- Produced valid JSON with exactly one fenced code block
- Correctly identified `verdict: "fail"` (the assembly is objectively broken)
- Named specific AC violations in rationale (D1–D5 + D7)
- Provided accurate `routing_hint: {"work_item_type": "implementation"}`
- Detected all planted defects

## Per-model notes

### Kimi K2.6 (ollama)
- Elapsed: 70.7s
- Rationale covered AC-02, AC-03, AC-05, AC-06, AC-07
- Also noted missing eviction logic (D7)

### DeepSeek v4 Pro (ollama)
- Elapsed: 30.8s (fastest)
- Rationale covered AC-02, AC-03, AC-05, AC-06, AC-07
- Noted `int()` truncation of refill (D4 detail)

### GLM 5.1 (z.ai)
- Elapsed: 38.6s
- Rationale covered AC-02, AC-03, AC-05, AC-06, AC-07
- Additional observation: "Integration tests are too weak to catch any of these" — shows meta-awareness of test-theater risk

## Decision

**All three Tier-A models are qualified for the `outcome_verifier` role.**

Default binding: same as `frontier_judge` — **K2 via opencode/fireworks** (proven in production, lowest latency among qualified models). DeepSeek and GLM are acceptable fallbacks.

No additional probe runs needed. The role can proceed to pipeline use.

## Artifacts

- Prompt: `src/factory/prompts/outcome_verifier.md`
- Assembly fixture: `tests/fixtures/capability-probe/reference_flawed_assembly.py`
- Integration-test fixture: `tests/fixtures/capability-probe/reference_flawed_integration_tests.py`
- Rubric: `tests/fixtures/capability-probe/_outcome_verifier_rubric.md`
- Probe script: `scripts/capability_probe_outcome_verifier.py`
- Raw outputs: `.factory/analysis/capability-probe-validation/outcome-verifier/`
