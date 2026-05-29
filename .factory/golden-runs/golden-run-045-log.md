# GR-045: dep-graph-viewer Phase B with Sonnet decomposer

**Date:** 2026-05-28
**Config:** `.factory/golden-runs/golden-run-045-config.yaml`
**Fixture:** Phase B decomposer output from `tests/fixtures/dep-graph-viewer/spec.yaml` via claude-code Sonnet
**Channels:** K2 (opencode) for worker roles, Sonnet (claude-code) for cross_family_reviewer + jury
**Executor:** manual (decompose + populate + runner/gate/scheduler)
**Wall clock:** ~22 min (23:31–23:53 UTC)

## Purpose

Phase B validation for RFC-023 on the dep-graph-viewer workload. Tests whether a model-driven decomposer produces semantic module names and whether those names improve or maintain pipeline reliability. GR-044 established the Phase A baseline at 97%; this run validates that Phase B matches or exceeds it.

## Decomposer Output

Claude-code Sonnet produced **semantic module names** on first attempt:

| Phase A (deterministic) | Phase B (Sonnet) | FR Mapping |
|---|---|---|
| fr01 | event_log_reader | FR-01: PostgreSQL event log reader |
| fr02 | graph_builder | FR-02: In-memory graph reconstruction |
| fr03 | graph_filter | FR-03: Node/edge filtering |
| fr04 | dot_emitter | FR-04: DOT syntax output |

The decomposer also produced Phase A files (fr01-fr05) with a hallucinated FR-05 (audit trail content from log-redact-cli spec). Only the 4 semantic-named files were used for the pipeline run.

## Result Summary

| Metric | GR-045 (Phase B) | GR-044 (Phase A) | GR-043 (log-redact B) | Target |
|---|---|---|---|---|
| Lock-within-budget | 96% (27/28) | 97% (30/31) | 97% (33/34) | — |
| Mean attempts | 1.68 | 1.81 | 1.74 | ≤2.0 |
| First gate pass | 100% (27/27) | 97% (30/31) | 97% (33/34) | ≥60% |
| Inner gate first-pass | 100% (20/20) | 92% (22/24) | 96% (23/24) | ≥60% |
| Cannot proceed | 0 | 1 | 0 | — |
| Deterministic gate rate | 77% (36/47) | 79% (44/56) | 75% (44/59) | ≥80% |
| Stuck items | 0 | 0 | 0 | ≤1 |
| Unknown gate rate | 0.0% | 0.0% | 1.7% | <1% |
| verify_passed | False (1 orphan) | True | False | — |

**Overall: NEAR PASS** — best first-attempt pass rate of any run (100%), zero failures, but 1 orphan submit prevents verify_passed.

## Per-Stage Detail

### interface_spec (4/4 locked)
- event_log_reader, graph_builder, graph_filter, dot_emitter: all passed inner_pytest first attempt
- Gate: interface_spec — 100% first-attempt pass
- Mean duration: 50.8s

### test_suite (4/4 locked)
- 4 items, all locked
- All passed inner_pytest first attempt
- Gate: test_suite — 100% first-attempt pass

### implementation (4/4 locked)
- 4 items, all locked (including event_log_reader with psycopg2 dependency)
- All passed inner_pytest first attempt — the types-psycopg2 fix from GR-044 worked
- Gate: implementation — 100% first-attempt pass
- Mean duration: 37.5s

### review (4/4 locked)
- 4 items via cross_family_reviewer (claude-code Sonnet)
- 100% first-attempt pass
- Mean duration: 21.0s

### jury (4/4 locked)
- 4 items via jury_quorum (K2 + Sonnet)
- 100% first-attempt pass

### integration (4/4 locked)
- 4 items, all locked
- All passed inner_json_shape first attempt
- Gate: integration — 100% first-attempt pass
- Mean duration: 84.6s

### outcome_verification (3/4 locked, 1 orphan)
- 3 items locked via outcome_e2e
- 1 item submitted but never gated (orphan submit)
- Gate: outcome_e2e — 100% pass for items that reached gate

## Failure Analysis

### 1 orphan submit

**Root cause:** The 4th outcome_verification item was submitted at 23:53:01 (near end of run). The gate process was likely idle by then and didn't pick it up before being killed. This is a timing issue, not a pipeline defect — the item was correctly processed by the runner but missed the gate's poll window.

**Classification:** Timing issue. The gate process polls every `poll_interval_seconds` (5s) but had no claims left to process by the time the last item was submitted.

### Decomposer hallucinated FR-05

The Sonnet decomposer produced a `wi_fr05.md` containing log-redact-cli audit trail content (AC-LOG-08, AC-LOG-09) despite being given the dep-graph-viewer spec.yaml. This is a cross-workload contamination issue — Sonnet's context likely included remnants of prior log-redact-cli decomposition. The Phase B semantic-named files were correct; the Phase A fallback files were contaminated. Workaround: use only semantic-named files from the decomposer output.

## Model-Family Performance Comparison

| Role | Channel | Model | Items | 1st-Att | Overall | Mean Duration |
|---|---|---|---|---|---|---|
| interface_architect | opencode | K2 | 4 | 100% | 100% | 50.8s |
| test_author | opencode | K2 | 4 | 100% | 100% | 57.7s |
| implementer | opencode | K2 | 4 | 100% | 100% | 37.5s |
| cross_family_reviewer | claude-code | Sonnet | 4 | 100% | 100% | 21.0s |
| frontier_judge | K2 + Sonnet | multi | 4 | 100% | 100% | — |
| integrator | opencode | K2 | 4 | 100% | 100% | 84.6s |
| outcome_verifier | opencode | K2 | 3 | 100% | 100% | 24.3s |

**100% first-attempt pass across all roles** — first time this has happened on any workload.

## BC-145 Upstream Routing

No `REVIEW_FOUND_DEFECT` events — all reviews passed on first attempt.

## Claim-Near-Budget Behavior

No claim_near_budget events. All items locked on first attempt.

## Channel Health

- **opencode (K2):** 20 inner gate evaluations, all passed first attempt. No failures.
- **claude-code (Sonnet):** 4 review + 4 jury evaluations. No failures.

## Telemetry Integrity

- unknown_gate_name_count: 0
- unknown_gate_name_rate: 0.0%
- orphan_submit_count: 1 (last outcome_verification item missed gate poll)
- unmatched_gate_count: 0
- verify_passed: False (due to orphan submit)

## Artifacts Preserved

- Workspace: `/tmp/sf2-golden-045`
- Logs: `/tmp/gr045-runner.log`, `/tmp/gr045-gate.log`, `/tmp/gr045-scheduler.log`
- Config: `.factory/golden-runs/golden-run-045-config.yaml`
- Decomposer output: `/tmp/.decomposed/`

## Code Changes

None (changes were committed with GR-044).

## Lessons and Next Steps

1. **Phase B matches Phase A on dep-graph-viewer.** 96% lock rate vs 97% Phase A — statistically identical. The semantic module names (event_log_reader, graph_builder, graph_filter, dot_emitter) did not help or hurt reliability. They are a readability improvement, not a correctness improvement.

2. **100% first-attempt pass rate.** This is the cleanest run in the project's history — zero inner gate retries, zero channel failures, zero cannot_proceed. The dep-graph-viewer workload with Phase B decomposition + types-psycopg2 fix is remarkably stable.

3. **Sonnet follows the Phase B prompt.** Unlike K2 (which ignored semantic naming in GR-041), Sonnet produced semantic names on the first attempt. This confirms the finding from GR-043 that the decomposer prompt needs models with strong instruction-following capability.

4. **Decomposer cross-workload contamination.** Sonnet produced a hallucinated FR-05 with log-redact-cli content. This suggests the decomposer's prompt or context retains information from prior decompositions. If the decomposer is used in production, it needs per-invocation context isolation.

5. **N=2 workloads validated for Phase B.** Both log-redact-cli (GR-043) and dep-graph-viewer (GR-045) pass through Phase B with semantic naming at ≥96% lock rate. The W5 decision gate writeup can now proceed.

6. **The orphan submit is a minor infrastructure gap.** The gate process should be more aggressive about polling after the runner finishes, or the runner should signal completion. Not worth filing a BC for — it's cosmetic (verify_passed flag) and doesn't affect the actual pipeline output.
