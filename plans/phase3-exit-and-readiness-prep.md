# Phase 3 Exit + Operational Readiness Prep — Implementation Plan

**Status:** obsolete — Phase 3 has exited (GR-020) and the pipeline is now in Phase 5 (GR-038 first ALL-PASS full DAG). The readiness items this plan proposed have either been actioned or superseded by RFC-017/019/020/021 (all implemented). Retained for historical reference.
**Author:** adversarial-reviewer
**Date:** 2026-05-12
**Origin:** synthesizes critiques from `debate/adversarial-readiness-001.md`; connects to BC-120, BC-126, BC-127, BC-108, and active RFCs.

## Scope

This plan covers the work between "present state (19 golden runs, 550 tests, 94% lock rate)" and "Phase 3 is demonstrably ready to produce software for specs it did not author."

It is organized into **four execution windows** plus a **go/no-go decision gate** at the end of Window D. Items are ordered by dependency: measurement before action, decision before implementation, validation before declaration.

Out-of-scope: Phase 4 (jury/race), Phase 5 (first real workload), Phase 6 (generalization). Those remain governed by spec §10.

## Current state recap

- 550 tests pass, 0 lint errors, 0 audit findings
- 19 golden runs executed (GR-001 through GR-019)
- Best result: GR-019 — 94% lock rate (15/16), 64% first-attempt inner-gate pass on K2-only
- Open breadcrumbs: 5 (1 critical-resolved-but-file-says-proposed, 1 high, 1 medium, 1 low — but status drift in BC-126/127)
- Channel fleet: 2 validated (Claude CC, OpenCode/K2), 2 failing (GLM, DeepSeek), 1 untested (Gemini)
- No Phase 3 exit criteria have been defined numerically
- BC-120 (implementer-initiated interface amendment) is the only remaining high-severity open proposal

## Window A — Define exit criteria and clean telemetry (1 day)

### A1. Define Phase 3 exit criteria

Author a spec amendment (spec.md §10, Phase 3 section) with a **three-layer metric framework**:

| Layer | Metric | Phase 3 Target | Role |
|---|---|---|---|
| **Contract / prompt quality** | First-attempt mechanical-gate pass rate | ≥60–70% on cert-watch full DAG | Leading indicator. Measures whether prompts and specs are clean enough that the implementer self-checks before returning. The 0%→64% jump between GR-015 and GR-019 was real signal. |
| **Operational success** | Lock-within-budget rate | ≥90% | Did the system actually deliver? |
| **Efficiency / brute-force detector** | Mean attempts to lock | ≤2.0 | Catches "lock by burning retries." GR-015 achieved 100% lock with 0% first-attempt; mean attempts ≈2.0 per item. This is the boundary between "structured retry" and "brute force." |

**Additional constraints:**
- **Stuck/orphan rate:** ≤1 stuck item per 16-work-item DAG, with automatic escalation after 2× mean wall-clock.
- **Gate-failure mode breakdown:** ≤10% of failures are "unknown" or "tool_not_found"; ≥80% are deterministic gate failures with clear `diagnostic_kind`.

**Why 60–70% for first-attempt, not 80%:** Factory’s production data shows adversarial validation "never succeeds on the first go" — but that applies to the **jury / cross-family review layer** (Phase 4), not the mechanical gate layer. SF2’s inner gate measures whether a slot-filling implementer can produce lint/type-check passing code. 60–70% is achievable without gate weakening. When jury gates arrive in Phase 4, first-attempt pass at the *jury* layer should be expected to drop sharply — that is when Factory’s wisdom applies.

**Rationale:** AGENTS.md has said "define Phase 3 exit criteria numbers" is the next concrete step for multiple sessions. Without a finish line, Phase 3 never ends.

**Validation:** The criteria must be test-encoded (see A4).

### A2. Fix breadcrumb status drift

Audit all open breadcrumb files against `breadcrumbs/README.md`. For each mismatch, reconcile:

- If the code is merged and working → update the breadcrumb file to `status: implemented`, move to `resolved/`
- If the code is merged but the design is still evolving → update to `status: in_progress`
- If the README is wrong → correct the README

**Specific items to reconcile:**
- BC-126: `README.md` says `implemented`; file says `proposed`; code `work_item_size_metrics.py` exists but the analysis report (`.factory/analysis/...`) does not. **Resolution:** Keep open until the analysis report exists. Update README to `in_progress`.
- BC-127: `README.md` says `implemented`; file says `proposed`; code `spec_lint.py` exists and `populate_work_items.py` does not yet call it (verify). **Resolution:** If populate does not call spec_lint, keep open. If it does, close.

**Validation:** After reconciliation, `grep 'status:' breadcrumbs/*.md` should match the README index exactly.

### A3. Telemetry: expose the three-layer metric stack

Update `telemetry.py` and `golden_run_nanny.py` report output:

- **Top section:** Lock-within-budget rate (operational success)
- **Second section:** Mean attempts to lock (efficiency / brute-force detector)
- **Third section:** First-attempt mechanical-gate pass rate, labeled as "leading indicator (contract quality)" per role and channel
- **Detail rows:** `retry_budget_burn` = total attempts / total items for the run

**Validation:** Run `make golden-run` on any config; the telemetry report must show all three metrics, with lock rate first and first-attempt rate labeled as a leading indicator.

## Window B — Fleet triage and channel validation (1–2 days)

### B1. Validate or disable untested channels

Execute one single-work-item smoke test per unvalidated channel:

- **GeminiCLIChannel:** Run `make golden-run` with a phase1 config pointing at Gemini on a single cert-watch-mini spec (`certificate_model`, no deps). If it passes within 10 minutes and produces a valid `.pyi`, the channel is validated. If it fails, emits empty output, or flakes, add a guard in `gemini_channel.py:invoke()` that raises `NotImplementedError("GeminiCLIChannel has not been validated in a golden run; see BC-108")`.
- **GLM-5.1 via OpenCode:** Re-run the GR-017 config on a single spec. If it still produces empty output or gets stuck, remove GLM from the default `FactoryConfig.phase3()` roles.
- **DeepSeek V4:** Re-run GR-018 on a single spec. Document the pass rate honestly. If <70%, mark as Tier C (probationary) in the spec table.

**Validation:** The spec §5 table must have a "Validated in GR" column. Every entry must cite a golden run or say `NOT VALIDATED`.

### B2. Default config reflects reality

Update `FactoryConfig.phase3()` to bind only validated channels:

- interface_architect → Claude CC or K2 (validated)
- test_author → K2 (validated)
- implementer → K2 (validated, best first-attempt rate)
- GLM, DeepSeek, Gemini removed from defaults until validated

**Validation:** `test_phase3.py` assertions updated to match the new defaults.

## Window C — Run measurement and act on the answer (2 days)

### C1. Execute BC-126 Phase A (measurement)

Run `scripts/work_item_size_metrics.py` against all surviving golden run substrates:

- Target: ≥100 work-item rows across ≥6 GRs
- Output: `.factory/analysis/2026-05-XX-work-item-granularity.md`
- Required analysis: correlation of `ac_count` vs `first_attempt_passed`, bucketed by AC count

**Validation:** The analysis report explicitly answers: *"Does size predict first-attempt failure? Where is the knee, if any?"*

### C2. Wire spec lint into populate (BC-127 completion)

If `spec_lint.py` exists but `populate_work_items.py` does not call it, complete the wiring:

- `populate_work_items.py` calls `spec_lint(config)` before creating work items
- `--skip-lint` and `--strict` flags honored
- If lint fails with errors, populate exits non-zero; no work items created

**Validation:** `test_spec_lint.py` end-to-end test passes against cert-watch fixtures.

### C3. Act on BC-126 answer

**Decision branches:**

- **Curve is flat** (no relationship): Close BC-126. No cap needed. Update AGENTS.md with the finding.
- **Knee exists** (e.g., first-attempt rate drops sharply above 7 ACs): Add `AC_SOFT_CAP` to `spec_lint.py` `check_ac_count_within_band`. Emit a warning (not error) for ACs > cap. Document the threshold in AGENTS.md.
- **Monotonically declining without knee:** Escalate to a design discussion in the next session. Do not invent a threshold without a clear knee.

**Validation:** Running spec lint on cert-watch specs produces deterministic findings. The next golden run's nanny report references the threshold if applicable.

## Window D — Structural improvements and adversarial fixtures (2 days)

### D1. Decision: BC-120 (interface amendment request)

**Two options, both acceptable, but one must be chosen:**

**Option A — Implement now (Phase 3):**
- Add `ARTIFACT_FILENAME_INTERFACE_AMENDMENT = "interface_amendment.json"` to constants
- Add structured output format to `implementer.md` prompt: when the implementer determines the interface is wrong, output JSON with `amendment_type`, `proposed_change`, `rationale`, `evidence`
- Runner detects `interface_amendment.json` artifact on `cannot_proceed`; adds `diagnostic_kind: "interface_amendment"`
- Principal reviews manually via the `cannot_proceed` queue

**Option B — Defer to Phase 4, but track:**
- Add telemetry metric: `interface_amendment_requests` (count of `cannot_proceed` items where the last gate failure is a deterministic mypy/pytest mismatch that the implementer could have reported)
- Add a note to AGENTS.md: "Phase 3 assumes interfaces are correct on first draft. If amendment request count becomes nonzero, BC-120 triggers immediately."

**Validation:** Either the code exists (Option A) or the telemetry dimension exists (Option B).

### D2. Integration test isolation

Fix the module-scoped `real_sub` fragility noted in Session 26 reflection:

- Change `real_sub` fixture in `test_integration_pipeline_shapes.py` from module-scoped to function-scoped, OR
- Add a cleanup step that resets the project state between tests, OR
- Accept the risk and document it with a breadcrumb.

**Validation:** Running integration tests in any order produces the same results.

## Go / No-Go Decision Gate

After Windows A–D, execute **GR-020** with the following decision criteria:

| Criterion | Threshold | Source |
|---|---|---|
| Lock-within-budget rate on cert-watch full DAG | ≥90% | A1 |
| Mean attempts to lock | ≤2.0 | A1 |
| First-attempt mechanical-gate pass rate | ≥60% | A1 |
| Zero unvalidated channels in default config | Yes | B2 |
| Spec lint runs and is deterministic | Yes | C2 |
| BC-126 analysis report exists and has a conclusion | Yes | C1 |
| No breadcrumb status drift | Yes | A2 |

**If all pass:** Phase 3 is declared complete. Proceed to Phase 4 planning (jury/race).

**If any fail:** The failing item becomes the next session's focus. Do not advance phases. Do not declare "Phase 3 complete with caveats."

## Out-of-scope (deferred with triggers)

| Item | Phase | Trigger |
|---|---|---|
| Mutation testing gate (RFC-007) | Phase 4–5 | First-attempt rate ≥80% consistently; then mutation gate becomes the next bottleneck |
| Pipeline checkpoint/resume (RFC-008) | Phase 3–5 | A golden run crashes and loses >30 min of progress |
| Interactive debugging inner loop (RFC-009) | Phase 5+ | 3+ consecutive GRs where pytest-in-inner-loop failures exceed 20% of total gate failures |
| Gate subprocess credential stripping (RFC-012) | Phase 5+ | Factory processes a spec from an untrusted source |
| Per-project venv isolation (RFC-006) | Phase 5 | First real workload has conflicting dependency versions |
| Adversarial / messy spec fixture | Phase 5 | Factory needs to prove it handles ambiguous specs from non-technical stakeholders (spec §1 mission) |

## Validation criteria for the plan itself

- [ ] Plan is reviewed and accepted/rejected by the principal within one session
- [ ] Every window has a test-encoded validation criterion
- [ ] No window depends on unvalidated channels
- [ ] Go/no-go criteria are binary (pass/fail), not subjective
- [ ] If go, the next commit updates spec.md §10 Phase 3 with the exit criteria
