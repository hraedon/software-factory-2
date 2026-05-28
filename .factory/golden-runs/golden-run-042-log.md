# GR-042: dep-graph-viewer Phase A baseline

**Date:** 2026-05-28
**Config:** `.factory/golden-runs/golden-run-042-config.yaml`
**Fixture:** `tests/fixtures/dep-graph-viewer` (Phase A deterministic, 4 FRs)
**Channels:** K2 (opencode) for worker roles, Sonnet (claude-code) for cross_family_reviewer + jury
**Executor:** agent_golden_run.py (monitoring aborted by channel_invoke_failed threshold; processes continued to completion)
**Wall clock:** ~30 min (18:28–18:58 UTC)

## Purpose

First pipeline run on the dep-graph-viewer workload. This is the third non-cert-watch fixture to go through the full pipeline (after log-redact-cli in GR-040/041/043). Validates that the pipeline handles a workload with (a) sequential FR dependencies (FR-03→FR-02, FR-04→FR-03), (b) external dependency on psycopg2-binary, and (c) database integration testing.

## Result Summary

| Metric | GR-042 (dep-graph-viewer) | GR-040 (log-redact-cli A) | GR-043 (log-redact-cli B) | Target |
|---|---|---|---|---|
| Lock-within-budget | 69% (11/16) | 96% (45/47) | 97% (33/34) | — |
| Mean attempts | 2.13 | 1.76 | 1.74 | ≤2.0 |
| First gate pass | 73% (11/15) | 100% (45/45) | 97% (33/34) | ≥60% |
| Inner gate first-pass | 79% (11/14) | 91% (31/34) | 96% (23/24) | ≥60% |
| Cannot proceed | 5 | 2 | 0 | — |
| Deterministic gate rate | 81% (26/32) | 76% (60/79) | 75% (44/59) | ≥80% |
| Stuck items | 0 | 0 | 0 | ≤1 |

**Overall: SOME FAIL** — lock rate degraded to 69% by channel reliability issues (3 review channel_failures + 1 interface_spec failure + 1 implementation gate exhaustion).

## Per-Stage Detail

### interface_spec (3/4 locked)
- 01275748, 88da02b6, 947e4403: all passed inner_pytest first attempt, submitted
- 69751fa7: claimed at 18:29, went to cannot_proceed at 18:31 (no inner gate events — model produced no valid artifact within timeout)
- Gate: interface_spec — 100% first-attempt pass for items that reached gate

### test_suite (4/4 locked)
- 4 items created from 3 locked interface_specs + 1 other source
- All passed inner_pytest first attempt
- Gate: test_suite — 100% first-attempt pass

### implementation (2/4 locked)
- 2 items passed inner_pytest and submitted successfully
- 2ee41b1d: exhausted 3 inner gate retries
  - Retry 0: inner_ruff failed (N806 variable naming: `Identifier` should be lowercase)
  - Retry 1: inner_pytest failed (psycopg2 connection error in test)
  - Retry 2: inner_mypy failed (Library stubs not installed for `psycopg2`)
  - Submitted with exhausted_retries, then re-claimed at attempt 3 → claim_near_budget → cannot_proceed
- 1 other implementation item may have been blocked by upstream cannot_proceed
- Gate: implementation — items that passed inner gate passed outer gate

### review (0/3 locked, 3 cannot_proceed)
- 179e2b26: channel_invoke_failed x2 (1-2s per attempt), cannot_proceed
- 7a8f608c: channel_invoke_failed x2 (1-2s per attempt), cannot_proceed
- 5c7445dc: channel_invoke_failed x2 (1-2s per attempt), cannot_proceed
- All failures: "Non-zero exit code" — channel returned error immediately
- Gate: no review items reached the gate

### jury, integration, outcome_verification (0 items)
- Pipeline stalled at review stage — no downstream items created

## Failure Analysis

### 1 interface_spec cannot_proceed (69751fa7)

**Root cause:** Model invocation produced no valid artifact. The item was claimed for 2.5 minutes (18:29–18:31) without any inner gate evaluation, then went directly to cannot_proceed. This suggests the opencode channel either timed out, produced unparseable output, or the model failed to generate a valid spec artifact.

**Classification:** CLASS-010 (Channel Reliability) instance.

### 1 implementation cannot_proceed (2ee41b1d)

**Root cause:** Triple inner gate failure — ruff naming violation (N806), pytest failure (psycopg2 connection in test), mypy failure (missing `types-psycopg2` stubs). The model generated code with a `psycopg2` dependency but the gate venv didn't have `types-psycopg2` installed. This is the same pattern seen in GR-041 (BC-008 class — gate venv environment mismatch).

The gate venv should install `psycopg2-binary` from requirements.txt and `types-psycopg2` should come from the stub resolution. Either the requirements.txt doesn't include `types-psycopg2` (it only has `psycopg2-binary>=2.9`) or the gate venv installation didn't pick it up.

**Classification:** Known limitation — the dep-graph-viewer workload requires psycopg2 stubs that aren't in requirements.txt. A future fix should either add stubs to requirements or have the gate venv resolver install type stubs automatically.

### 3 review channel_invoke_failed (179e2b26, 7a8f608c, 5c7445dc)

**Root cause:** Unknown — the channel returned "Non-zero exit code" within 1-2 seconds for all 6 attempts (2 per item). This is too fast for a model invocation timeout, suggesting the claude-code CLI itself crashed or returned an error immediately. Possible causes:
1. claude-code auth expired mid-run
2. claude-code rate limiting (but 1-2s is unusual for rate limit)
3. Transient infrastructure issue

The review role uses claude-code with Sonnet. K2 (opencode) items processed successfully during the same window, ruling out a general infrastructure problem.

**Classification:** CLASS-010 (Channel Reliability) instance.

## Model-Family Performance Comparison

| Role | Channel | Model | Items | 1st-Att | Overall | Mean Duration |
|---|---|---|---|---|---|---|
| interface_architect | opencode | K2 | 4 | 100%* | 75% | 36.7s |
| test_author | opencode | K2 | 4 | 100% | 100% | 48.3s |
| implementer | opencode | K2 | 4 | 75% | 50% | — |
| cross_family_reviewer | claude-code | Sonnet | 3 | 0% | 0% | — |
| frontier_judge | — | — | 0 | — | — | — |

*interface_architect 100% first-attempt for the 3 items that completed; 1 item produced no artifact.

## BC-145 Upstream Routing

No `REVIEW_FOUND_DEFECT` events — reviews failed at channel level before producing any findings.

## Claim-Near-Budget Behavior

4 claim_near_budget events: 2ee41b1d (implementation, attempt 3), 179e2b26 (review, attempt 3), 7a8f608c (review, attempt 3), 5c7445dc (review, attempt 3). All correctly hard-transitioned to cannot_proceed.

## Channel Health

- **opencode (K2):** 14 inner gate evaluations. 1 interface_spec produced no artifact (69751fa7). 1 implementation exhausted retries. Otherwise stable.
- **claude-code (Sonnet):** 3 review invocations attempted, all failed with non-zero exit code within 1-2 seconds. No successful invocations.

## Telemetry Integrity

- unknown_gate_name_count: 6 (all 6 channel_fail events)
- unknown_gate_name_rate: 18.8% (above 1% target)
- orphan_submit_count: 0
- unmatched_gate_count: 0
- verify_passed: False (due to unknown gate rate)

## Artifacts Preserved

- Workspace: `/tmp/sf2-golden-042` (preserved with `--no-cleanup`)
- Logs: `.factory/logs/gr042/`
- Config: `.factory/golden-runs/golden-run-042-config.yaml`

## Code Changes Made During Session

1. **Lint fix** — `decomposer_model.py:70`: split long `log.info()` call across multiple lines; `ruff format` on 3 files.
2. **spec.md AC format fix** — Reformatted dep-graph-viewer `spec.md` acceptance criteria from bullet-list format (`- **AC-DGV-01** [FR-01]: ...`) to heading format (`## AC-DGV-01\n\n...`) to satisfy spec_lint. The linter's bullet parser only supports `AC-\d+` (no prefix).
3. **breadcrumbs/README.md cleanup** — Moved BC-217 and BC-218 from Open section to Resolved table (pre-existing issue flagged in prior reflection).

## Lessons and Next Steps

1. **dep-graph-viewer is harder than cert-watch.** The psycopg2 dependency and database integration create a more challenging environment. The implementation stage had legitimate failures (type stubs, connection errors) that cert-watch never encounters.

2. **Channel reliability dominated this run.** 3 of 5 cannot_proceed items were from channel_fail on review items. If claude-code had worked, the lock rate would be ~80% (13/16) — still below GR-043's 97%, but much more respectable.

3. **Review stage is a reliability bottleneck.** With only one reviewer channel (claude-code), any claude-code issue kills all review items. Consider adding a fallback channel for the reviewer role, or making the reviewer channel configurable per-attempt.

4. **The dep-graph-viewer fixture needs `types-psycopg2` in requirements.txt.** The gate venv installs `psycopg2-binary` but not its type stubs. Adding `types-psycopg2>=2.9` to the fixture's requirements.txt would fix the mypy failure on 2ee41b1d.

5. **Re-run recommended** with: (a) `types-psycopg2` in fixture requirements, (b) verified claude-code health, (c) potentially a second reviewer channel as fallback. The pipeline architecture is sound — the failures are environmental, not structural.

6. **BC-209 partially addressed.** This is the third non-cert-watch golden run (after GR-040, GR-043). dep-graph-viewer is the most architecturally complex fixture yet (database dependency, sequential FR chain).
