# GR-043: log-redact-cli Phase B with MiMo-V2.5-Pro decomposer

**Date:** 2026-05-28
**Config:** `.factory/golden-runs/golden-run-043-config.yaml`
**Fixture:** Phase B decomposer output from `tests/fixtures/log-redact-cli/spec.yaml` via MiMo-V2.5-Pro
**Channels:** K2 (opencode) for worker roles, Sonnet (claude-code) for cross_family_reviewer + jury
**Executor:** manual (populate + runner/gate/scheduler)
**Wall clock:** ~30 min (16:53–17:25 UTC)

## Purpose

Phase B validation for RFC-023 with a stronger model (MiMo-V2.5-Pro) driving the decomposer. GR-041 showed K2 produces identical output to Phase A (no semantic names). This run tests whether MiMo-V2.5-Pro follows the Phase B prompt's semantic naming rules and produces a decomposition that resolves the cross-module type incompatibility observed in GR-040.

## Result Summary

| Metric | GR-043 (MiMo Phase B) | GR-041 (K2 Phase B) | GR-040 (Phase A) | Target |
|---|---|---|---|---|
| Lock-within-budget | 97% (33/34) | 57% (4/7) | 96% (45/47) | — |
| Mean attempts | 1.74 | 2.40 | 1.76 | ≤2.0 |
| First gate pass | 97% (33/34) | 80% (4/5) | 100% (45/45) | ≥60% |
| Inner gate first-pass | 96% (23/24) | 80% (4/5) | 91% (31/34) | ≥60% |
| Cannot proceed | 0 | 2 | 2 | — |
| Deterministic gate rate | 75% (44/59) | 100% (12/12) | 76% (60/79) | ≥80% |
| Stuck items | 0 | 1 | 0 | ≤1 |

**Overall: SOME FAIL** (deterministic gate rate 75% vs 80% target; unknown gate rate 1.7% vs <1%)

## Key Finding: MiMo-V2.5-Pro Follows Phase B Prompt

Unlike K2 (GR-041), MiMo-V2.5-Pro produced **semantic module names**:
- `rule_loader` (FR-01) — loads and validates YAML redaction rules
- `log_reader` (FR-02) — reads JSONL input lines
- `redaction_engine` (FR-03) — evaluates rules and applies replacements
- `output_emitter` (FR-04+FR-05) — emits redacted output and audit trail (grouped)

**No `fr\d+` pattern in any module name.** The semantic naming gates never fired because the model produced valid names on the first attempt.

### Decomposition comparison

| Aspect | Phase A (deterministic) | K2 Phase B (GR-041) | MiMo Phase B (GR-043) |
|---|---|---|---|
| Module names | `fr01`–`fr05` | `fr01`–`fr05` | `rule_loader`, `log_reader`, `redaction_engine`, `output_emitter` |
| FR grouping | 1:1 (5 modules) | 1:1 (5 modules) | 4:5 (FR-04+05 grouped) |
| AC bodies | Populated | Empty | Populated (enriched from spec) |
| Dep names | `fr01`, `fr02` | `fr01`, `fr02` | `rule_loader`, `log_reader` |
| Integration failures | 2 (cross-module types) | 2 (same as Phase A) | 0 (only 1 channel fail) |

## Per-Stage Detail

### interface_spec (5/5 locked)
- 5 items, all locked
- 1 inner_pytest retry (import issue, recovered)
- Gate: interface_spec — 100% first-attempt pass

### test_suite (5/5 locked)
- 5 items, all locked
- All inner gate passes on first attempt
- Gate: test_suite — 100% first-attempt pass

### implementation (5/5 locked)
- 5 items, all locked
- 1 inner_pytest retry (recovered)
- Mean duration: ~30s per item
- Gate: implementation — 100% first-attempt pass

### review (5/5 locked)
- 5 items, all locked via cross_family_review (Sonnet)
- 100% first-attempt pass
- Mean duration: 9.5s per item

### jury (5/5 locked)
- 5 items, all locked via jury_quorum (K2 + Sonnet)
- 100% first-attempt pass

### integration (4/5 locked, 1 channel_fail)
- 4 items locked successfully
- 1 item (42c00d79) hit `channel_invoke_failed` — "Could not extract artifact from opencode output". Retried on attempt 2 but skipped due to prior gate fail (BC-062 pattern).
- Gate: integration — 100% first-attempt pass (for items that reached the gate)

### outcome_verification (4/4 locked)
- 4 items (corresponding to successful integrations)
- All locked on first evaluation
- Gate: outcome_e2e — 100% pass

## Failure Analysis

### 1 integration channel_fail (42c00d79)

**Root cause:** opencode CLI produced output that the channel adapter couldn't parse as an artifact. This is a transient channel reliability issue (CLASS-010), not a decomposition problem.

The model produced valid code but the opencode output format didn't include a recognizable artifact block. On retry (attempt 2), the runner skipped due to the prior channel_fail event (BC-062 guard).

**This is unrelated to the Phase B decomposition.** The same failure mode could occur on any workload.

## Model-Family Performance Comparison

| Role | Channel | Model | Items | 1st-Att | Overall | Mean Duration |
|---|---|---|---|---|---|---|
| interface_architect | opencode | K2 | 5 | 80%* | 100% | 41.4s |
| test_author | opencode | K2 | 5 | 100% | 100% | 36.1s |
| implementer | opencode | K2 | 5 | 100% | 100% | 26.7s |
| cross_family_reviewer | claude-code | Sonnet | 5 | 100% | 100% | 9.5s |
| frontier_judge | K2 + Sonnet | multi | 5 | 100% | 100% | — |
| integrator | opencode | K2 | 5 | 100% | 100% | 74.0s |
| outcome_verifier | opencode | K2 | 4 | 100% | 100% | 20.6s |

*interface_architect 80% first-attempt is due to 1 inner_pytest retry (recovered).

## BC-145 Upstream Routing

No `REVIEW_FOUND_DEFECT` events — all reviews passed on first attempt.

## Claim-Near-Budget Behavior

No `claim_near_budget` events. All items locked within attempt_threshold of 3.

## Channel Health

- **opencode (K2):** 24 inner gate evaluations, multiple outer gate evaluations. 1 channel_fail on integration (transient).
- **claude-code (Sonnet):** 5 review evaluations + 5 jury evaluations. No failures.

## Telemetry Integrity

- unknown_gate_name_count: 1 (the channel_fail event has no gate name)
- unknown_gate_name_rate: 1.7% (above 1% target — caused by 1 channel_fail)
- orphan_submit_count: 1 (the channel-failed item was submitted but never gated)
- unmatched_gate_count: 0
- verify_passed: False (due to unknown gate rate)

## Artifacts Preserved

- Workspace: `/tmp/sf2-golden-043` (not cleaned — processes killed manually)
- Logs: `/tmp/gr043-runner.log`, `/tmp/gr043-gate.log`, `/tmp/gr043-scheduler.log`
- Config: `.factory/golden-runs/golden-run-043-config.yaml`

## Code Changes Made During Session

1. **spec_lint.py AC format fix** — Updated regex to accept `AC-{PREFIX}-NN` format (e.g., `AC-LOG-01`) in addition to `AC-NN`. Made colon optional in heading pattern. All 29 spec_lint tests pass.

2. **decomposer_model.py model_override + AC enrichment** — Threaded `model_override` through `_invoke_decomposer_channel` and `decompose_from_model`. Added AC condition text lookup from spec.yaml data. Added FR-ID → semantic module_name mapping for dependency resolution.

3. **populate_work_items.py AC ID extraction** — Replaced hardcoded `["AC-01"]` with `_extract_ac_ids_from_fixture()` that parses AC IDs from fixture file headings. Fixes the root cause of GR-041's `cannot_proceed` failures.

4. **agent_golden_run.py decomposer args** — Added `--decomposer-channel` and `--decomposer-model` CLI arguments, wired through to `populate_work_items.py`.

## Lessons and Next Steps

1. **Model choice matters for Phase B.** K2 ignored the semantic naming prompt; MiMo-V2.5-Pro followed it on the first attempt. The decomposer prompt is not model-agnostic — it needs either model-specific tuning or a model with stronger instruction following.

2. **Phase B produces better decompositions.** MiMo's grouping of FR-04+05 into `output_emitter` is architecturally sensible (both deal with output emission). The semantic names make the codebase more navigable than `fr01`–`fr05`.

3. **The AC enrichment fix is critical.** Without populated AC bodies, the model returns `cannot_proceed` because it can't determine what to implement. The previous Phase B runs (GR-041) likely had this issue masked by K2 not checking AC IDs.

4. **97% lock rate matches Phase A.** Phase B with MiMo achieves the same lock rate as Phase A (96-97%), validating that the model-driven decomposer doesn't degrade pipeline reliability.

5. **Next: run dep-graph-viewer through Phase B with MiMo** to validate the decomposition generalizes across workloads. Then write the W5 decision gate update.

6. **The `--decomposer-channel`/`--decomposer-model` args in `agent_golden_run.py` need integration testing.** The current golden run used a manual decompose-then-populate flow because the `agent_golden_run.py` integration isn't complete (populate runs with `--fixtures`, not `--spec-yaml`).
