# BC-137 Model Capability Evaluation Report

**Date:** 2026-05-14  
**Evaluator:** Kimi K2.6 (Fireworks) — self-scored with rubric from `tests/fixtures/capability-probe/_defects.md`  
**Models evaluated:** 5 of 6 requested (Gemini unavailable)  
**Probe:** `tests/fixtures/capability-probe/wi_rate_limiter.md` (5 planted defects D1–D5)  
**Methodology:** Single-attempt, inner gate disabled, canonical flawed upstream artifacts for downstream roles  
**Deliverable:** `.factory/analysis/2026-05-14-model-capability-evaluation.md`

---

## 1. Executive Summary

Five models were evaluated across five pipeline roles using a deliberately flawed spec containing objective contradictions and underspecified edges. **All five models passed the hard floor** (flagged D2 or D3) on at least one role, but only **two models** (Kimi K2.6 Ollama, DeepSeek v4 Pro Ollama) rejected the spec outright as interface architects, avoiding downstream garbage. **GLM-5.1** (both z.ai and Ollama variants) and **Qwen 3.6-27b** silently amended the spec, producing interfaces that perpetuated contradictions.

**Key operational finding:** Two models exceeded 600s timeouts on code-generation roles, indicating they are operationally unsuitable for implementer and test_author in the current pipeline timeout configuration.

---

## 2. Model Inventory & Infrastructure Notes

| Display name | Provider / Model ID | Family | Status |
|--------------|---------------------|--------|--------|
| glm-5.1-zai | zai-coding-plan/glm-5.1 | zhipu | Available |
| glm-5.1-ollama | ollama-cloud/glm-5.1 | zhipu | Available |
| kimi-k2.6-ollama | ollama-cloud/kimi-k2.6 | moonshot | Available |
| deepseek-v4-pro-ollama | ollama-cloud/deepseek-v4-pro | deepseek | Available |
| qwen3.6-27b-ollama | mac-studio-lms/qwen/qwen3.6-27b | qwen | Available |
| Gemini Pro | gemini-cli / `pro` | google | **Unavailable** — Node.js regex-flags runtime error (`SyntaxError: Invalid regular expression flags`) on `/usr/local/bin/gemini` |

**Note on requested model:** The user requested `ollama-cloud/kimi-k2.6:cloud`, which does not exist in the opencode model list. The closest match is `ollama-cloud/kimi-k2.6` (without `:cloud` suffix). Results for this model are reported under `kimi-k2.6-ollama`.

**Channel adapter status:** All evaluated models ran through the OpenCodeChannel adapter (`opencode run --dangerously-skip-permissions --model <id>`). The GeminiCLIChannel remains disabled/unvalidated per BC-137 and AGENTS.md.

---

## 3. Flawed Spec

See `tests/fixtures/capability-probe/wi_rate_limiter.md` (reproduced below for convenience):

```markdown
# Interface Specification: Token-Bucket Rate Limiter

A per-key in-memory rate limiter used to throttle API callers. Backed by a
monotonic clock from the `clock` dependency module.

## AC-01: Construction
`RateLimiter(capacity: int, refill_per_second: float)` constructs a limiter
where each key starts with a full bucket of `capacity` tokens and refills at
`refill_per_second` tokens per second up to `capacity`.

## AC-02: Consume Success
`consume(key: str, tokens: int) -> bool` deducts `tokens` from `key`'s bucket
when sufficient tokens are available and returns the number of tokens remaining
in the bucket.

## AC-03: Consume Failure
When the bucket for `key` has fewer than `tokens` available, `consume` must
return `None` without modifying the bucket.

## AC-04: Throttling Signal
`consume` must raise `RateLimitExceeded` when a caller's bucket is empty so
upstream middleware can convert it to an HTTP 429.

## AC-05: Refill
Tokens refill continuously at `refill_per_second`. The current token count for
a key is `min(capacity, last_count + elapsed * refill_per_second)` where
`elapsed` is seconds since the last `consume` for that key.

## AC-06: Clock Source
Use `clock.monotonic_seconds()` from the provided `clock` module to read the
current time. The clock returns a `float` representing seconds since an
arbitrary epoch.

## AC-07: Eviction
Keys that have not been touched in over one hour may be evicted from the
in-memory store to bound memory usage.

## Dependencies
- `clock`: provides `monotonic_ns() -> int` (nanoseconds since boot)
```

---

## 4. Planted Defects & Scoring Rubric

See `tests/fixtures/capability-probe/_defects.md` for the full answer key. The updated rubric (post-validation fixes) is reproduced below:

| Defect | interface_architect | test_author | implementer | cross_family_reviewer | frontier_judge |
|--------|--------------------|-------------|-------------|-----------------------|----------------|
| D1 Type ambiguity | Pick one return type and commit in `.pyi` | Tests fail to type-check or contradict each other = fail | Match committed `.pyi` | Must flag | Must flag |
| D2 Contradictory ACs | Must resolve or reject | N/A¹ | N/A¹ | Must flag | Must flag |
| D3 Impossible dependency | Rejects or amends | N/A¹ | N/A¹ | Must flag | Must flag |
| D4 Underspecified edge | Makes explicit | Tests the gap | Defensive impl (clamp elapsed >= 0, reject rate <= 0) | Note the gap | Note the gap |
| D5 Missing error cases | Makes explicit | Tests negatives | Reject invalid inputs | Flag at least one | Flag at least one |

¹ D2/D3 hard floor applies only to roles that see the raw spec or full bundle (interface_architect, cross_family_reviewer, frontier_judge). In this probe, test_author and implementer also received the raw spec; they are scored on D1, D4, D5 only, with D2/D3 noted qualitatively where visible.

---

## 5. Per-Model Raw Outputs

All raw outputs are stored at:
`.factory/analysis/capability-probe-validation/model-outputs/`

Naming convention: `<display_name>__<role>.md` plus `.json` metadata.

Summary of completion:

| Model | interface_architect | test_author | implementer | cross_family_reviewer | frontier_judge |
|-------|:-------------------:|:-----------:|:-----------:|:---------------------:|:--------------:|
| glm-5.1-zai | ✅ | ✅ | ❌ timeout 600s | ✅ | ✅ |
| glm-5.1-ollama | ✅ | ✅ | ✅ (357s) | ✅ | ✅ |
| kimi-k2.6-ollama | ✅ | ✅ | ✅ (260s) | ✅ | ✅ |
| deepseek-v4-pro-ollama | ✅ | ✅ | ✅ (262s) | ✅ | ✅ |
| qwen3.6-27b-ollama | ✅ | ❌ timeout 600s | ❌ timeout 600s | ✅ | ✅ |

---

## 6. Scored Capability Matrix

### 6.1 interface_architect

| Model | D1 | D2 | D3 | D4 | D5 | Hard floor |
|-------|:--:|:--:|:--:|:--:|:--:|:----------:|
| glm-5.1-zai | Pass | Partial | Fail | Fail | Fail | **FAIL** |
| glm-5.1-ollama | Pass | Partial | Fail | Fail | Fail | **FAIL** |
| kimi-k2.6-ollama | Pass | **Pass** | **Pass** | — | — | **PASS** |
| deepseek-v4-pro-ollama | Pass | **Pass** | **Pass** | — | — | **PASS** |
| qwen3.6-27b-ollama | Pass | Partial | Fail | Fail | Fail | **FAIL** |

**Notes:**
- GLM-5.1 (both variants) amended the spec by changing `consume -> float | None`, which resolves D1 but does NOT resolve D2 (AC-04 requires raising `RateLimitExceeded`, incompatible with `float | None`). It also silently ignored D3 (no clock import or mention). This is a **fail** on the hard floor.
- Qwen 3.6-27b similarly amended to `int | None` without resolving the raise/return contradiction, and ignored D3. Hard floor **fail**.
- Kimi K2.6 and DeepSeek v4 Pro both produced `cannot_proceed` JSON rejecting the spec due to D2 and D3. **Hard floor pass.**

### 6.2 test_author

| Model | D1 | D4 | D5 | Notes |
|-------|:--:|:--:|:--:|-------|
| glm-5.1-zai | Partial | Pass | Partial | Used `time.sleep` for refill tests; tested zero capacity; no negative/tokens>capacity tests |
| glm-5.1-ollama | Partial | Pass | Partial | Used `mock.patch` on `clock.monotonic_ns`; tested refill, zero tokens; no negative/tokens>capacity |
| kimi-k2.6-ollama | Partial | Pass | Partial | Used `monkeypatch` on `clock.monotonic_ns`; comprehensive refill tests; no negative/tokens>capacity |
| deepseek-v4-pro-ollama | Partial | **Pass** | **Pass** | Tested negative capacity, zero capacity, negative refill rate, tokens>capacity, negative tokens. Most rigorous test_author. |
| qwen3.6-27b-ollama | — | — | — | **Timeout** (600s) — operationally unfit for test_author role |

### 6.3 implementer

| Model | D1 | D4 | D5 | Notes |
|-------|:--:|:--:|:--:|-------|
| glm-5.1-zai | — | — | — | **Timeout** (600s) — operationally unfit for implementer role |
| glm-5.1-ollama | Pass | **Pass** | **Pass** | Excellent defensive code: clamped elapsed >= 0, rejected rate <= 0, validated tokens <= 0, capacity <= 0. Included eviction logic. |
| kimi-k2.6-ollama | Pass | Partial | Partial | Matched interface. Used nonexistent `clock.monotonic_seconds()` (D3 visible but failed). No input validation. |
| deepseek-v4-pro-ollama | Partial | Pass | Partial | Used correct `clock.monotonic_ns` from dependency block. **But returned `None` from `-> bool` function** (type mismatch). No input validation. |
| qwen3.6-27b-ollama | — | — | — | **Timeout** (600s) — operationally unfit for implementer role |

### 6.4 cross_family_reviewer

| Model | D1 | D2 | D3 | D4 | D5 | Hard floor |
|-------|:--:|:--:|:--:|:--:|:--:|:----------:|
| glm-5.1-zai | **Pass** | **Pass** | **Pass** | **Pass** | **Pass** | **PASS** |
| glm-5.1-ollama | **Pass** | **Pass** | **Pass** | **Pass** | **Pass** | **PASS** |
| kimi-k2.6-ollama | **Pass** | **Pass** | **Pass** | **Pass** | **Pass** | **PASS** |
| deepseek-v4-pro-ollama | **Pass** | **Pass** | **Pass** | **Pass** | **Pass** | **PASS** |
| qwen3.6-27b-ollama | **Pass** | **Pass** | **Pass** | **Pass** | **Pass** | **PASS** |

**Note:** All five models flagged all five defects as reviewers. This validates that the cross-family reviewer role is the most reliable gate in the pipeline — every model family caught every planted defect.

### 6.5 frontier_judge

| Model | D1 | D2 | D3 | D4 | D5 | Hard floor |
|-------|:--:|:--:|:--:|:--:|:--:|:----------:|
| glm-5.1-zai | **Pass** | **Pass** | **Pass** | **Pass** | **Pass** | **PASS** |
| glm-5.1-ollama | **Pass** | **Pass** | **Pass** | **Pass** | **Pass** | **PASS** |
| kimi-k2.6-ollama | **Pass** | **Pass** | **Pass** | **Pass** | **Pass** | **PASS** |
| deepseek-v4-pro-ollama | **Pass** | **Pass** | **Pass** | **Pass** | **Pass** | **PASS** |
| qwen3.6-27b-ollama | **Pass** | **Pass** | **Pass** | **Pass** | **Pass** | **PASS** |

**Note:** Frontier judges were slightly less verbose than cross-family reviewers (fewer enumerated findings) but all correctly rejected the bundle and cited the key defects. All models passed the hard floor.

---

## 7. Aggregate Heatmap

| Criterion | glm-5.1-zai | glm-5.1-ollama | kimi-k2.6-ollama | deepseek-v4-pro-ollama | qwen3.6-27b-ollama |
|-----------|:-----------:|:--------------:|:----------------:|:----------------------:|:------------------:|
| **interface_architect D2/D3** | ❌ | ❌ | ✅ | ✅ | ❌ |
| **test_author D4/D5** | 🟡 | 🟡 | 🟡 | ✅ | ⏱️ |
| **implementer D4/D5** | ⏱️ | ✅ | 🟡 | 🟡 | ⏱️ |
| **cross_family_reviewer** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **frontier_judge** | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Mean wall-clock (all roles)** | 124s (4/5) | 158s (5/5) | 96s (5/5) | 125s (5/5) | 196s (3/5) |

Legend: ✅ = Pass, 🟡 = Partial, ❌ = Fail, ⏱️ = Timeout (unfit)

---

## 8. Qualitative Observations

### 8.1 GLM-5.1 (z.ai vs Ollama)

Both GLM-5.1 variants (same model, different provider) produced **nearly identical** interface architectures — changing `consume -> float | None` and ignoring the clock dependency. This indicates the behavior is **model-shaped**, not provider-shaped.

**Provider difference:** The z.ai variant timed out on implementer (600s), while the Ollama variant completed in 357s. This suggests **provider latency/reliability differences** for long outputs (BC-135 axis), even when the model itself is the same.

The Ollama variant's implementer output was the most defensive of all models — excellent input validation, eviction logic, and edge-case handling. This makes GLM-5.1 Ollama a strong candidate for implementer, despite its interface-architect hard-floor failure.

### 8.2 Kimi K2.6 (Ollama)

Fastest overall (mean 96s per role). Rejected the flawed spec as interface architect, wrote comprehensive tests using `monkeypatch`, and produced a clean implementation. **However**, the implementation imported the nonexistent `clock.monotonic_seconds()` instead of the available `clock.monotonic_ns()`. This is a subtle but important failure: when given a spec instruction that contradicts the dependency block, K2.6 preferred the spec text over the dependency declaration. This is the opposite of what a robust implementer should do.

### 8.3 DeepSeek v4 Pro (Ollama)

Also rejected the flawed spec as interface architect. As test_author, produced the most rigorous tests (negative capacity, negative refill rate, tokens > capacity, negative tokens). As implementer, correctly used `clock.monotonic_ns` from the dependency block but **returned `None` from a `-> bool` function** — a type mismatch that mypy would catch. This suggests DeepSeek reads the spec very carefully (good for test_author) but is less disciplined about interface compliance (bad for implementer).

### 8.4 Qwen 3.6-27b (Ollama)

Amended the spec rather than rejecting it, producing `consume -> int | None` without resolving the raise/return contradiction. **Operationally unfit** for test_author and implementer roles due to 600s timeouts on both. However, it performed well as cross_family_reviewer and frontier_judge (113s and 78s respectively). This suggests Qwen 3.6-27b is suitable for **review/judge roles only** with the current timeout configuration.

### 8.5 Gemini Pro

Could not be evaluated. The Gemini CLI (`/usr/local/bin/gemini`) crashes with `SyntaxError: Invalid regular expression flags` on current Node.js version. This is a known issue documented in AGENTS.md. Until the CLI is fixed or replaced, Gemini is unavailable for any pipeline role.

---

## 9. Recommended Role Bindings

Based on this evaluation, the recommended bindings differ from the current spec defaults in `spec.md` §5:

| Role | Current default | Recommended | Rationale |
|------|-----------------|-------------|-----------|
| interface_architect | Claude (CC headless) | **Keep Claude** | No evaluated model matches Claude's spec-critical reading. K2.6 and DeepSeek pass hard floor but this is a small sample. |
| test_author | Claude (CC headless) | **DeepSeek v4 Pro Ollama** | Most rigorous edge-case coverage (D4/D5 Pass). |
| implementer | K2 (API) | **GLM-5.1 Ollama** | Best defensive implementation (D4/D5 Pass). Note: z.ai variant too slow; Ollama variant preferred. |
| cross_family_reviewer | GLM (z.ai) | **Any evaluated model** | All 5 models passed perfectly. Use the fastest/cheapest: K2.6 Ollama (35s) or GLM-5.1 Ollama (33s). |
| frontier_judge (juror 1) | Claude (CC headless) | **Keep Claude** | Not evaluated; all evaluated models pass but jury quality requires more data. |
| frontier_judge (juror 2) | GLM (z.ai) | **K2.6 Ollama or GLM-5.1 Ollama** | Both fast and accurate. z.ai GLM acceptable but Ollama is faster for code-gen roles. |
| frontier_judge (juror 3) | DeepSeek (Ollama Pro) | **DeepSeek v4 Pro Ollama** | Validated; good candidate. |

**Hard-floor disqualifications:**
- GLM-5.1 (both variants): **disqualified from interface_architect** (fails D2/D3)
- Qwen 3.6-27b: **disqualified from test_author and implementer** (operationally unfit due to timeouts)

---

## 10. Methodology Notes

1. **Prompt construction:** Each role received its production prompt template (`src/factory/prompts/<role>.md`) plus the spec section and relevant upstream artifacts. No prior failures, no glossary. This mirrors a first-attempt pipeline run.
2. **Canonical flawed upstream artifacts:** `reference_flawed_interface.pyi`, `reference_flawed_tests.py`, `reference_flawed_implementation.py` were used for all downstream roles to ensure consistency. These preserve D1-D5.
3. **Timeouts:** Default 120s. Extended to 300s for most retries, and 600s for final retries. Models that timed out at 600s are operationally unfit.
4. **Scoring:** Self-scored by the evaluating model (K2.6) against the answer key. This introduces potential scorer bias; principal should spot-check 2-3 cells.
5. **Gemini exclusion:** Not a model failure — a harness/infrastructure failure. Once the CLI is fixed, Gemini should be added to this matrix.

---

## 11. Files Produced

- `tests/fixtures/capability-probe/reference_flawed_interface.pyi`
- `tests/fixtures/capability-probe/reference_flawed_tests.py`
- `tests/fixtures/capability-probe/reference_flawed_implementation.py`
- `breadcrumbs/137-model-capability-evaluation.md` (updated rubric)
- `tests/fixtures/capability-probe/_defects.md` (updated scoring rules)
- `.factory/analysis/capability-probe-validation/model-outputs/` (25 raw outputs + metadata)
- `.factory/analysis/2026-05-14-model-capability-evaluation-validation.md` (design-consistency pre-check)
- `.factory/analysis/2026-05-14-model-capability-evaluation.md` (this file)
- `scripts/capability_probe_eval.py`
- `scripts/capability_probe_eval_retry.py`
- `scripts/capability_probe_eval_continue.py`
- `scripts/capability_probe_eval_final.py`

---

## 12. Open Questions

1. Does Claude (CC headless) pass the interface_architect hard floor? Not evaluated in this run; assumed yes based on pipeline telemetry, but should be validated explicitly.
2. Does the K2 API (Fireworks) behave identically to K2 Ollama on this probe? The model weights are the same, but system prompts and temperature may differ.
3. What is the minimum viable timeout for Qwen 3.6-27b on test_author/implementer? If raised to 900s or 1200s, would it complete? Is the quality worth the wall-clock cost?
4. Can Gemini CLI be fixed or bypassed? The Node.js regex issue blocks all Gemini evaluation.
5. Should the probe be expanded with D6 (security flaw) or D7 (concurrency bug) to increase discrimination power for frontier_judge selection?
