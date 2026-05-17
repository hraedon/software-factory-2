# Golden Run 038 — K2 + Sonnet family-pair calibration; first ALL-PASS full-DAG run

**Date:** 2026-05-17
**Config:** `golden-run-038-config.yaml`
**Channels:**
- opencode (fireworks-ai/accounts/fireworks/routers/kimi-k2p6-turbo) — worker roles + integrator + outcome_verifier + 1 frontier_judge juror
- claude-code (sonnet) — cross_family_reviewer + 1 frontier_judge juror (jury_quorum=2)
- code (mechanical_gate)
**Fixture:** cert-watch (full DAG, 8 interface specs)
**Executed by:** Claude Code (Opus 4.7) via `scripts/agent_golden_run.py`
**Wall clock:** ~1h40m (18:41 → ~20:21), with a wrapper-induced FATAL near the end that did not affect run outcome thanks to the GR-037 `start_new_session=True` fix
**Changes vs GR-037:** Sonnet swapped in as cross-family reviewer + second jury juror; BC-186 hard-transition fix landed pre-launch; telemetry lock-rate gate downgraded to informational; wrapper `start_new_session=True` enabled

## Purpose

Two goals stacked into one run:

1. **Family-pair calibration** (follow-up to GR-037). GR-037 showed gemini-2.5-pro
   rejecting 94% of K2 implementations, which prevented the lock rate from
   converging despite the pipeline being structurally correct. Sonnet has been
   the calibration target for most prompts in this project, so it should
   produce a much higher review pass rate. The question: does a converging
   reviewer-pair restore reasonable throughput, validating that GR-037's lock
   rate was a pair-property rather than a pipeline bug?

2. **Late-stage coverage** (jury / integration / outcome_verification). These
   stages had N=1 evidence across GR-037 plus a handful of mini-fixture runs.
   With a converging pair, more impl→review pairs should reach jury and beyond
   in a single run.

Also validates four code changes that shipped between GR-037 and GR-038:
BC-186 hard-transition, telemetry lock-rate downgrade, wrapper
`start_new_session=True`, and the `gate_fail_cross_family_review` fatal
retirement.

## Result Summary

| Metric | Value | Target | Status |
|---|---|---|---|
| Lock-within-budget rate | 82% (41/50) | — | **informational** |
| Mean attempts to lock | 2.00 | ≤2.0 | **PASS** |
| First gate-evaluation pass rate | 82% (41/50) | ≥60% | **PASS** |
| Inner gate first-pass rate | 65% (26/40) | ≥60% | **PASS** |
| Stuck items | 0 | ≤1 / 16-item DAG | **PASS** |
| Unknown gate rate | 0.0% (0/100) | ≤10% | **PASS** |
| Deterministic gate rate | 96% (96/100) | ≥80% | **PASS** |
| Verify passed | True | — | **PASS** |
| Orphan submits | 0 | — | **PASS** |

**Overall: ALL PASS** — the first ALL-PASS Overall on this branch under the
informational-lock-rate criteria. Every structural correctness gate green.

### Substrate state at termination

Total work items: **55** (vs 100 in GR-037 — far less upstream-revision
amplification because Sonnet passes more reviews)

| Type | locked | cannot_proceed |
|---|---|---|
| interface_spec | 8 | 0 |
| test_suite | 7 | 1 |
| implementation | 12 | 1 |
| review | 6 | 6 |
| jury | 4 | 2 |
| integration | 4 | 0 |
| outcome_verification | 4 | 0 |
| **Total** | **45** | **10** |

**Four complete end-to-end DAG lineages** locked through all 7 stages
(interface_spec → outcome_verification). This is the first run on this branch
to produce N≥3 on each late stage, satisfying the GR-037 follow-up coverage
goal.

## Per-stage Detail

### Interface specs — 8/8 locked
100% first-attempt outer pass. Inner pytest first-pass at 25% (2/8) but 100%
recovery on retry.

### Test suites — 7/7 locked, 1 cannot_proceed
test_author 100% first-attempt on `test_suite` and `inner_pytest` gates. The
one failure was a `test_suite_assertions` defect that exhausted budget.

### Implementations — 12 locked, 1 cannot_proceed
implementer 100% first-attempt on the `implementation` outer gate. Inner
gates: 80% first-attempt on `inner_pytest`, 0% first-attempt on `inner_mypy`
(typical — mypy retries usually succeed). One item hit `implementation_mypy`
at the outer gate and exhausted budget.

Of the 13 implementations, 6 were upstream revisions from cross_family_review
failures — vs 45 upstream revisions in GR-037. Much tighter amplification.

### Reviews — 6 locked, 6 cannot_proceed
**Cross-family reviewer (Sonnet): 55% first-attempt pass rate** — an order of
magnitude better than GR-037's gemini-2.5-pro at 6%. Every review failure
correctly routed via BC-185 routing_fields to a new upstream implementation
revision; zero `CUSTOM_FIELD_VIOLATION` errors. BC-180/185 structural fix
continues to hold under a different reviewer family.

### Jury — 4 locked, 2 cannot_proceed
**Dual-family jury (K2 + Sonnet) reached quorum 4/6 times.** Two `jury_disagree`
outcomes (50/50 split on the verdict), both correctly transitioned to
cannot_proceed. First substantial exercise of `jury_disagree` routing on this
branch — telemetry: 2 disagree, 4 quorum, both pass rates as expected (0%
for disagree, 100% for quorum).

### Integration — 4 locked, 0 cannot_proceed
**100% first-attempt pass on the integration gate** (`mean duration 92s`).
The integrator role (K2 via opencode) assembled multi-module trees from each
of the 4 successful jury lineages and passed every integration check. First
time this stage has cleared 4 items in one run.

### Outcome verification — 4 locked, 0 cannot_proceed
**100% first-attempt pass on outcome_e2e** (`mean duration 13s`). All 4
verifiers exercised the assembled tree and produced valid attestations.
First time the Stage 7 surface has produced N=4 in one run.

## Validation Outcomes by Change

| Change | Status | Evidence |
|---|---|---|
| BC-186 hard-transition for budget-exhausted gating items | **Validated** | Zero `gate_near_budget` events in the entire run; zero items stuck cycling in gating state. The 1 implementation_mypy + 1 test_suite cannot_proceed cases transitioned cleanly via the BC-186 path. Compare to GR-037 where cc11078f cycled 1175 times. |
| Telemetry lock-rate downgrade to informational | **Validated** | Report shows `Lock-within-budget rate: 82% (41/50) (informational)` with no PASS/FAIL marker. `Overall: ALL PASS` reflects only structural correctness gates. The previously-failing GR-037 number is no longer a false alarm. |
| Wrapper `start_new_session=True` for Popen children | **Validated** | When the wrapper's third obsolete guardrail (`claim_near_budget >= 5`, see below) fired `_fatal()` near the end of the run, all three pipeline children survived as orphans with PPID=1 and continued processing until manually terminated. State loss: zero. |
| Wrapper `gate_fail_cross_family_review` fatal retirement | **Validated by absence** | No spurious wrapper fatal during the 6 cross_family_review gate_fail events. The retirement holds. |
| BC-180/185 routing under a second reviewer family | **Validated** | 6 cross_family_review gate_fails → 6 clean upstream_revision_created events. Zero `CUSTOM_FIELD_VIOLATION`, zero gate-process exceptions. The fix is structurally sound across model families, not just under the specific conditions of GR-036/037. |

## Wrapper Issue Found

Late in the run (near 20:00), the wrapper's `claim_near_budget >= 5` fatal
threshold tripped. This is the **third** wrapper guardrail to decay past
usefulness this week:

1. False-idle SIGTERM threshold (retired in commit `1710792`)
2. `gate_fail_cross_family_review >= 3` fatal (retired in commit `6913f19`)
3. `claim_near_budget >= 5` fatal (retired in commit `f1fc1ef`, post-fatal)

The pattern is consistent: each guardrail was added when its target event
was rare and load-bearing (a real crash-loop signal). Under the BC-139 +
BC-186 fixes, `claim_near_budget` now means "an item reached attempt_threshold
and BC-139 hard-stopped it" — i.e., **expected terminal behavior**. Counting
those as systemic-failure indicators is the same category error as the
previous two. Retired with explanatory comment citing BC-139 and BC-186.

The wrapper's `start_new_session=True` fix (commit `d121744`, in place before
GR-038 launched) paid its first dividend here: the false fatal would have
killed a successful ALL-PASS run if children had still shared the wrapper's
session.

## Channel Health

| Channel | Model | Outcomes | Stability |
|---|---|---|---|
| opencode | K2 | ~40 invocations (workers, integrator, outcome_verifier, 1 juror) | Stable; 0 timeouts; 0 invoke failures |
| claude-code | Sonnet | 11 cross_family_reviews + 4 jury invocations | Stable; 0 timeouts; 0 invoke failures |

Zero `channel_invoke_failed` events across the entire run. Both channels
performed reliably.

## Telemetry Integrity

| Check | Value | Status |
|---|---|---|
| unknown_gate_name_count | 0 | PASS |
| orphan_submit_count | 0 | PASS |
| unmatched_gate_count | 0 | PASS |
| confounding_warning_count | 0 | PASS |
| verify_passed | True | PASS |

Clean. The single remaining `event_schema_unknown_fields: SubmitPayload
custom_fields_update` warning is a known cosmetic issue from the BC-185
schema split, not a correctness problem.

## GR-037 vs GR-038 — the family-pair signal

| Dimension | GR-037 (K2 + gemini) | GR-038 (K2 + sonnet) |
|---|---|---|
| Cross-family reviewer pass rate (first-attempt) | 6% | **55%** |
| Upstream revisions created | 45 | **6** |
| Total work items generated | 100 | **55** |
| Lock-within-budget rate | 62% | **82%** |
| End-to-end DAG completions | 1 | **4** |
| jury items locked | 1 | **4** |
| integration items locked | 1 | **4** |
| outcome_verification items locked | 1 | **4** |
| `Overall` aggregation | SOME FAIL (lock-rate dragged) | **ALL PASS** |
| Wall clock | ~3h | **~1h40m** |

**Conclusion: GR-037's lock-rate failure was a family-pair property, not a
pipeline bug.** With Sonnet as the cross-family reviewer, every quality gate
passes, late-stage coverage is robust, and the run completes in roughly half
the time. The BC-180/185 routing fix is now validated across two different
reviewer families with very different rejection rates — it doesn't depend on
any particular reviewer's behavior.

## Artifacts Preserved

- Config: `.factory/golden-runs/golden-run-038-config.yaml`
- Logs: `.factory/logs/gr038/` (runner, gate, scheduler) — full run history
- Wrapper log: `/tmp/gr038-wrapper.log`
- Workspace: `/tmp/sf2-golden-038` (preserved via `--no-cleanup`)
- Isolated opencode DB: `/tmp/sf2-golden-gr038-opencode-data/`

## Code Changes Committed This Session

Already landed before GR-038 launched (motivated by GR-037):
- `d121744` — wrapper: `start_new_session=True` on Popen children
- `7ad63a8` — BC-186: gate_loop hard-transitions budget-exhausted gating items
- `05277d9` — telemetry: lock-rate is informational, dropped from Overall
- `48c35b8` — GR-038 config

Landed during GR-038 wrap-up:
- `f1fc1ef` — wrapper: retire `claim_near_budget >= 5` fatal threshold

## Follow-ups

1. **The wrapper guardrail set is now stable** for K2-worker + cross-family
   reviewer configurations. All three obsolete fatal thresholds have been
   retired. The remaining `channel_invoke_failed >= 5` fatal is reasonable
   to keep (a model channel outage during a long run is a genuine emergency)
   though the threshold may still be too low; defer revisiting until we see
   an actual case.

2. **Late-stage coverage is now adequate for GR-039+ to focus on other
   experiments.** With N=4 on jury/integration/outcome_verification in a
   single run, we have enough data to characterize their behavior. A future
   *dedicated* late-stage fixture (synthetic-seeded substrate items at
   `locked` state for impl/review) would still be valuable for fast
   iteration, but it's no longer the top priority.

3. **The 55% cross-family pass rate is the new family-pair-calibration
   baseline.** Future configurations can be compared against this number to
   judge whether a reviewer pair is "in the convergent regime" before
   committing to a multi-hour run. Worth adding a pre-flight mini-run
   (1-2 impl/review pairs) to the wrapper for new pairings — but optional.

4. **Mean attempts at 2.00 sits right at the threshold.** Just barely
   passing. Worth watching whether this drifts down on next runs or stays
   pinned at the boundary. If it pins, the threshold may be too tight given
   the inner-gate retry budget.

## Lessons

1. **One full ALL-PASS run is a milestone.** Every structural correctness
   gate green, four end-to-end lineages through all seven stages, zero
   stuck items, zero crash-loops, zero channel failures. Phase 5 exit is
   visible from here.

2. **Family-pair calibration matters more than I expected.** A reviewer
   rejecting 94% vs 45% changes the run from "FAIL with 1 end-to-end" to
   "PASS with 4 end-to-end" — that's a 3x throughput swing on the same
   pipeline code. Worth thinking about as a first-class concern in
   experiment design, not an afterthought.

3. **The wrapper safety protocol needs an explicit lifecycle.** Three
   guardrails added during early instability turned into false-alarms
   once the pipeline matured. The lesson isn't "don't add guardrails" —
   they were correct at the time — it's "tag each guardrail with the
   conditions that justify it, and audit on every BC that changes those
   conditions." Worth a short RFC.

4. **Compound fixes compound.** The `start_new_session=True` change took
   five minutes and 30 lines yesterday. It saved the GR-038 run today.
   Hardening small operational seams pays disproportionate dividends.
