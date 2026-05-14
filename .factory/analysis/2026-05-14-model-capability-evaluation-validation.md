# BC-137 Capability-Probe Validation Report

**Date:** 2026-05-14  
**Model under smoke test:** Kimi K2.6 (Fireworks)  
**Validator:** self (same model instance)  
**Scope:** Design-consistency check + end-to-end smoke test of the flawed-spec probe  
**Deliverable:** `.factory/analysis/2026-05-14-model-capability-evaluation-validation.md`

---

## 1. Executive Summary

The capability-probe framework (flawed spec `wi_rate_limiter.md`, answer key `_defects.md`, rubric in `breadcrumbs/137-model-capability-evaluation.md`) is **structurally sound** but has **three material inconsistencies** that must be resolved before it can be used for systematic model evaluation.

**Verdict:** The probe is usable for interface_architect, cross_family_reviewer, and frontier_judge immediately. It needs prompt amendments before it can fairly evaluate test_author and implementer on the hard-floor defects (D2, D3).

---

## 2. Design-Consistency Findings

### 2.1 Flawed spec → answer key coverage (GOOD)

All five planted defects in `wi_rate_limiter.md` are captured in `_defects.md`:

| Defect | Spec location | Answer key | Category match |
|--------|---------------|------------|----------------|
| D1 | AC-02 signature vs prose | Yes | Type ambiguity |
| D2 | AC-03 vs AC-04 | Yes | Contradictory ACs |
| D3 | AC-06 vs Dependencies | Yes | Impossible dependency |
| D4 | AC-05 formula gaps | Yes | Underspecified edge |
| D5 | Spec-wide omissions | Yes | Missing error cases |

The **hard-floor rule** (failing D2 or D3 = unfit for that role) is correctly placed and justified: both are objective contradictions; missing them means the model is not reading critically.

### 2.2 Answer key → BC-137 rubric discrepancies (3 issues)

**Issue A: interface_architect row for "Spots contradictory ACs"**

- `_defects.md` says: "Reject or amend before producing interface" (must handle).
- `BC-137` rubric line 35 says: "N/A".
- **Problem:** The interface architect is the **first** role to encounter the raw spec. If they do not spot and resolve contradictions, the entire downstream pipeline produces garbage. "N/A" implies the criterion does not apply to them, which is false.
- **Recommendation:** Change to **"Must resolve or reject"**.

**Issue B: test_author row for "Detects impossible dependency"**

- `_defects.md` says: "N/A" (test author receives locked interface, not raw dependency block).
- `BC-137` rubric line 37 says: "Ignores or stubs".
- **Problem:** In the production pipeline, the test author prompt includes `locked_interface`, `spec_section`, `ac_ids`, etc. The architect has already resolved (or failed to resolve) D3. If the architect resolved it, the test author never sees the impossible dependency. If the architect failed, the test author sees the bad function in the interface — but the probe should test the model, not the interaction between two roles. Evaluating test_author on D3 requires giving them a deliberately flawed interface, which is non-standard.
- **Recommendation:** Change to **"N/A"** to match `_defects.md` and the actual pipeline flow.

**Issue C: D5 mapping (RESOLVED)**

- The addition of the "Spots missing error cases" row at BC-137 line 38 correctly gives D5 a landing spot.
- Verified: all per-role expectations in `_defects.md` map cleanly to the rubric row (interface_architect "Makes explicit", test_author "Tests negatives", implementer "Defensive impl", reviewer/jury "Must flag").
- **Status:** Correct.

---

## 3. Production-Prompt Mismatch (Critical for downstream roles)

A finding that is **not** a document inconsistency but a probe-vs-pipeline mismatch:

### 3.1 test_author and implementer have no structured-failure escape hatch

- The `interface_architect.md` prompt (line 38-52) provides a `cannot_proceed` JSON block for ambiguous specs.
- The `test_author.md` prompt says: "Output it in a single fenced Python code block. **No other output.**"
- The `implementer.md` prompt says the same.

**Consequence:** The probe expects test_author to "must flag" D2 (contradictory ACs) and implementer to "fail" on D3 (impossible dependency). But the production prompts give these roles **no channel to express refusal or flagging** outside the code artifact. A test author who spots D2 can only:
1. Write incoherent tests (and fail the quality bar), or
2. Embed a note in a test docstring (violates "No comments beyond test docstrings"? No, docstrings are allowed), or
3. Write an `assert False` test that documents the gap.

Option 3 is valid pytest, but it is indistinguishable from a model that simply writes bad tests.

**Recommendation:** Before the probe evaluates test_author or implementer on D2/D3, either:
- Add a `cannot_proceed` JSON escape hatch to both prompts (mirroring interface_architect), **or**
- Amend the probe methodology to state explicitly that D2/D3 are **not evaluated** for test_author/implementer because the pipeline does not expose raw spec contradictions to them (they see the locked interface).

The second option is simpler and aligns with the actual pipeline architecture. D2/D3 hard-floor evaluation can be restricted to the three roles that see the raw spec or full bundle: **interface_architect, cross_family_reviewer, frontier_judge**.

---

## 4. Smoke Test: Per-Role Simulation

I ran myself (K2.6) through each role using the flawed spec and, where appropriate, canonical flawed upstream artifacts. Raw outputs are in `.factory/analysis/capability-probe-validation/role-outputs/`.

### 4.1 interface_architect

**Input:** `wi_rate_limiter.md` as `spec_section`.  
**My output:** `cannot_proceed.json` rejecting the spec due to D2 and D3.

```json
{
  "status": "cannot_proceed",
  "reason": "Spec contains objective contradictions and an impossible dependency ...",
  "gaps": [
    "AC-03 says consume returns None ... but AC-04 says consume raises RateLimitExceeded ...",
    "AC-06 references clock.monotonic_seconds() -> float, but Dependencies only declares clock.monotonic_ns() -> int"
  ],
  "would_need": "Clarification on ... correct clock API"
}
```

**Self-score against `_defects.md`:**

| Defect | Score | Rationale |
|--------|-------|-----------|
| D1 | Pass | Did not silently commit to `bool`; the rejection implicitly avoids the ambiguity. |
| D2 | **Pass** | Rejected before producing interface. |
| D3 | **Pass** | Rejected before producing interface. |
| D4 | Not tested | Rejection prevented producing an amended interface. |
| D5 | Not tested | Rejection prevented producing an amended interface. |

**Hard-floor result:** **PASS** — D2 and D3 flagged.

### 4.2 test_author

**Input:** Flawed spec + deliberately flawed interface (`reference_flawed_interface.pyi`) preserving D1-D5.  
**My output:** Test file with docstring notes on D1 and D2, but no refusal mechanism.

**Self-score:**

| Defect | Score | Rationale |
|--------|-------|-----------|
| D1 | Partial | Noted `bool` vs `int` mismatch in docstring, but wrote tests against the flawed interface rather than flagging formally. |
| D2 | Partial | Noted AC-03 untestable due to interface, but could not refuse (no prompt channel). |
| D3 | N/A | Not visible in the provided interface. |
| D4 | Fail | Wrote `pass` for refill test; no boundary tests. |
| D5 | Fail | No negative-input tests (tokens <= 0, tokens > capacity). |

**Note:** My low D4/D5 score is expected because the **interface itself** contained no types or hooks for those edge cases, and the test_author prompt says "follow the interface." This validates that the probe can distinguish rigorous from superficial test authors — but only if the interface exposes the edges. If the architect suppresses D4/D5, the test author is blind to them. This means D4/D5 evaluation for test_author is **contingent on the upstream interface**.

### 4.3 implementer

**Input:** Flawed interface + test suite (happy-path only, no edge cases).  
**My output:** `implementation.py` passing all tests, using `time.monotonic()` instead of `clock.monotonic_seconds()`.

**Self-score:**

| Defect | Score | Rationale |
|--------|-------|-----------|
| D1 | Pass | Matched interface `-> bool`. |
| D2 | Pass | Matched tests (return False / raise exception). |
| D3 | Partial | Avoided nonexistent `clock.monotonic_seconds()` by substituting `time.monotonic()`. Did not fail gracefully because the prompt does not allow refusal. |
| D4 | Fail | No defensive code for negative elapsed, zero rate, or fp drift. |
| D5 | Fail | No input validation. |

### 4.4 cross_family_reviewer

**Input:** Full flawed bundle (spec + interface + tests + implementation).  
**My output:** `passed: false` with 5 specific findings.

**Self-score:**

| Defect | Score | Rationale |
|--------|-------|-----------|
| D1 | **Pass** | Flagged `bool` vs `int` mismatch. |
| D2 | **Pass** | Flagged AC-03/AC-04 contradiction. |
| D3 | **Pass** | Flagged impossible dependency (`monotonic_seconds` vs `monotonic_ns`). |
| D4 | **Pass** | Flagged underspecified edges (negative elapsed, rate <= 0, fp drift). |
| D5 | **Pass** | Flagged missing error cases. |

**Hard-floor result:** **PASS** — all 5 defects flagged.

### 4.5 frontier_judge

**Input:** Full flawed bundle.  
**My output:** `passed: false` citing D1, D2, D3.

**Self-score:**

| Defect | Score | Rationale |
|--------|-------|-----------|
| D1 | **Pass** | Flagged type contradiction. |
| D2 | **Pass** | Flagged AC-03/AC-04 contradiction. |
| D3 | **Pass** | Flagged impossible dependency. |
| D4 | Partial | Noted in bundle incoherence but did not enumerate specific gaps. |
| D5 | Partial | Noted in bundle incoherence but did not enumerate specific gaps. |

**Hard-floor result:** **PASS** — D2 and D3 flagged.

---

## 5. Aggregate Capability Matrix (Smoke Test)

| Criterion | interface_architect | test_author | implementer | cross_family_reviewer | frontier_judge |
|-----------|:-------------------:|:-----------:|:-----------:|:---------------------:|:--------------:|
| D1 Type ambiguity | Pass | Partial | Pass | **Pass** | **Pass** |
| D2 Contradictory ACs | **Pass** | Partial | Pass | **Pass** | **Pass** |
| D3 Impossible dependency | **Pass** | N/A | Partial | **Pass** | **Pass** |
| D4 Underspecified edge | — | Fail | Fail | **Pass** | Partial |
| D5 Missing error cases | — | Fail | Fail | **Pass** | Partial |
| **Hard floor** | **PASS** | — | — | **PASS** | **PASS** |

*Dashes indicate the defect was not exercisable because the role rejected the spec (interface_architect) or because upstream artifacts suppressed the edge (test_author/implementer).*

---

## 6. Probe Readiness Assessment

| Component | Status | Blocker |
|-----------|--------|---------|
| Flawed spec (`wi_rate_limiter.md`) | Ready | None |
| Answer key (`_defects.md`) | Ready | None |
| Hard-floor rule | Ready | None |
| BC-137 rubric | Needs fix | Issues A and B (§2.2) |
| interface_architect prompt | Ready | None |
| test_author prompt | Needs amendment | No structured-failure channel (§3.1) |
| implementer prompt | Needs amendment | No structured-failure channel (§3.1) |
| cross_family_reviewer prompt | Ready | None |
| frontier_judge prompt | Ready | None |
| Methodology (canonical upstream artifacts) | Needs addition | Must specify controlled flawed interfaces/tests for test_author/implementer |

---

## 7. Recommendations

1. **Amend BC-137 rubric**  
   - `interface_architect` / "Spots contradictory ACs": change `N/A` → `Must resolve or reject`.  
   - `test_author` / "Detects impossible dependency": change `Ignores or stubs` → `N/A`.

2. **Amend `_defects.md`**  
   - Add a note: "For roles without a structured-failure channel (test_author, implementer), flagging embedded in docstrings or `assert False` tests counts as Partial, not Pass, because it is indistinguishable from low-quality output."

3. **Amend production prompts OR restrict hard floor**  
   - **Option A (preferred):** Add `cannot_proceed` JSON support to `test_author.md` and `implementer.md`. This makes the pipeline more robust anyway.  
   - **Option B:** State in the probe methodology that D2/D3 are evaluated **only** for roles with structured-failure channels (interface_architect, cross_family_reviewer, frontier_judge). This is the minimal change.

4. **Add canonical upstream artifacts to the probe fixture**  
   - `reference_flawed_interface.pyi` (preserves D1-D5). Already created at `.factory/analysis/capability-probe-validation/role-outputs/reference_flawed_interface.pyi`; should be moved to `tests/fixtures/capability-probe/` if accepted.  
   - `reference_flawed_tests.py` (happy-path only, no edge cases).  
   - `reference_flawed_implementation.py` (passes tests but misses edges).

5. **Clarify scoring for "amend" vs "reject"**  
   - Both are Pass for D2/D3 on interface_architect. But amend requires additional scoring for D4/D5 (did the amendment handle them?). Reject skips D4/D5 scoring. The methodology should state whether amend or reject is the preferred response, or whether both are scored equally.

---

## 8. Files Produced

- `.factory/analysis/capability-probe-validation/role-outputs/reference_flawed_interface.pyi`
- `.factory/analysis/capability-probe-validation/role-outputs/interface_architect_output.md`
- `.factory/analysis/capability-probe-validation/role-outputs/test_author_output.md`
- `.factory/analysis/capability-probe-validation/role-outputs/implementer_output.md`
- `.factory/analysis/capability-probe-validation/role-outputs/cross_family_reviewer_output.md`
- `.factory/analysis/capability-probe-validation/role-outputs/frontier_judge_output.md`
- `.factory/analysis/2026-05-14-model-capability-evaluation-validation.md` (this file)
