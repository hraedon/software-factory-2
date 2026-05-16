# Golden Run 035 — Full cert-watch DAG, retries=3, K2+Qwen dual-family jury

**Date:** 2026-05-16
**Config:** `golden-run-035-config.yaml`
**Channels:**
- opencode (fireworks-ai/accounts/fireworks/routers/kimi-k2p6-turbo) — worker roles + integrator + outcome_verifier
- opencode (mac-studio-lms/qwen/qwen3.6-27b) — cross_family_reviewer + 1 frontier_judge juror
- opencode (fireworks-ai/accounts/fireworks/routers/kimi-k2p6-turbo) — 1 frontier_judge juror (jury_quorum=2)
**Fixture:** cert-watch (full DAG, 8 interface specs)
**Executed by:** OpenCode agent via `scripts/agent_golden_run.py`
**Wall clock:** ~4 hours across 4 attempts
**Changes vs GR-034:** Full cert-watch DAG (was cert-watch-mini); same model/channel bindings

## Purpose

Validate whether the 95% lock rate and 100% integration lock from GR-034 (cert-watch-mini, 3 items) generalizes to the full cert-watch DAG (8 interface specs, ~32-39 total items). If integration holds at scale, this is Phase 5 exit material.

## Result Summary

| Metric | Value | Target | Status |
|---|---|---|---|
| Total work items | 32 | — | — |
| Locked | 24 (75%) | ≥90% | **FAIL** |
| Cannot proceed | 5 | — | — |
| Stuck | 3 | ≤1 per 16-item DAG | **FAIL** |
| Mean attempts to lock | 2.31 | ≤2.0 | **FAIL** |
| First gate-evaluation pass rate | 83% (24/29) | ≥60% | **PASS** |
| Inner gate first-pass rate | 63% (19/30) | ≥60% | **PASS** |
| Unknown gate rate | 0.0% (0/67) | ≤10% | **PASS** |
| Deterministic gate rate | 100% (67/67) | ≥80% | **PASS** |
| Verify passed | False | — | **FAIL** (orphan_submit_count=2) |

**Overall: FAIL** — does not meet Phase 5 exit criteria. Run aborted by wrapper guardrail (`claim_near_budget ≥ 5`).

## Execution History

### Attempt 1 (07:08 – 08:08, 60 min)
- Killed by bash timeout (3600s).
- Telemetry at timeout: 34/39 locked (87%), 3 stuck, 1 cannot_proceed.
- **Critical bug discovered:** `test_suite_ref` missing in `ensure_upstream_revision` caused `CUSTOM_FIELD_VIOLATION` when gate process tried to create upstream implementation revisions from failed reviews/juries. This led to gate process crashes and cycling claims (attempts 90–970 observed on some items).

### Attempt 2 (08:15 – 08:48, 33 min)
- Wrapper declared idle after 90s of no log lines (model call hung).
- Telemetry: 9/13 locked (69%), 3 stuck, 1 cannot_proceed.
- Incomplete; runner blocked on long opencode call for implementer item.

### Attempt 3 (08:50 – 10:50, 120 min)
- Killed by bash timeout (7200s).
- Runner blocked on opencode call for 1+ hour. Gate process cycling on `create_work_item` error every 5s (3944 gate log lines).
- **Second bug discovered:** After fixing `test_suite_ref`, `upstream_revision_of` and `review_findings` were also rejected as "Unknown fields" by workflow validation.

### Attempt 4 (10:54 – 11:42, 48 min)
- Both prior bugs fixed. Fresh project created with updated workflow.
- Runner progressed to 24/32 locked (75%).
- **Third bug discovered:** `upstream_revision_of` declared as `work_item_ref` with `target_work_item_type: implementation`. Substrate validated that the referenced work item must be of type `implementation`. But `upstream_revision_of` stores the SOURCE work item ID (which is `review` or `jury`), causing `CUSTOM_FIELD_VIOLATION: Field 'upstream_revision_of' references work item of type 'review', expected 'implementation'`.
- This caused the gate process to crash-loop on failed reviews: claim, crash, release, reclaim (attempts 92–237 observed).
- Wrapper tripped `claim_near_budget ≥ 5` guardrail and killed the run.

## Per-stage Detail (Attempt 4, best-progress attempt)

### Interface specs (8 items)
8/8 locked. Inner gate first-pass: 50% (4/8), all recovered on retry. No stuck items.

### Test suites (8 items)
7/8 locked, 1 cannot_proceed. `inner_test_collect` failure on 2 items (pytest collection error).

### Implementations (7 items)
5/7 locked, 2 cannot_proceed.
- `implementation_mypy` failure: `fastapi` import-not-found (2 iterations). Root cause: interface spec imports `fastapi` but project venv does not include it.
- `implementation_pytest` failure: assertion error on `test_upload_certificate_accepts_pem` (3 iterations exhausted).

### Reviews (5 items)
2/5 locked, 2 stuck in gating (attempt 94–237 cycling), 1 new.
- Stuck reviews caused by `upstream_revision_of` type mismatch bug (see Failure Analysis).
- 1 new review (`FR-02 TLS Scanning`) not yet claimed when run aborted.

### Jury (2 items)
2/2 locked. Dual-family jury (K2 + Qwen), quorum=2, both reached quorum.

### Integration (2 items)
0/2 locked, 2 cannot_proceed.
- `integration_mypy` fail on 1 item.
- `integration_pytest` fail on 1 item.
- Integration stage did not lock any items on the full DAG.

## Failure Analysis

### 1. `test_suite_ref` missing in upstream revision (Attempt 1)
**Root cause:** `ensure_upstream_revision` in `scheduler.py` copied `interface_ref` and `dependency_refs` from the source work item, but not `test_suite_ref`. The workflow requires `test_suite_ref` on `implementation` work items. Substrate rejected the `create_work_item` call.
**Fix:** Added `test_suite_ref` propagation in `scheduler.py`. Committed as `41ba1fa`.

### 2. `upstream_revision_of` / `review_findings` not declared in workflow (Attempt 3)
**Root cause:** `ensure_upstream_revision` adds `upstream_revision_of` and `review_findings` to custom_fields, but `phase2.yaml`'s `implementation` work item type did not declare these fields.
**Fix:** Added both fields to `implementation` type in `phase2.yaml`. Committed as `f0bb66a`.

### 3. `upstream_revision_of` type mismatch (Attempt 4)
**Root cause:** Declared `upstream_revision_of` as `work_item_ref` with `target_work_item_type: implementation`. Substrate validates that the referenced work item matches the target type. But `upstream_revision_of` stores the ID of the SOURCE work item (review/jury), not the upstream type.
**Fix:** Changed `upstream_revision_of` from `work_item_ref` to `string` in `phase2.yaml`. Committed as `555f85d`.

### 4. `fastapi` import-not-found in implementation mypy
**Root cause:** Interface spec for `fr04_web_api` references `fastapi` types, but the project venv does not include `fastapi`. Mypy fails with `import-not-found`.
**Status:** Not fixed. The project venv is built from the fixture's requirements, but `fastapi` is not included. This is a fixture-level dependency gap.

### 5. Integration stage 0/2 locked
**Root cause:** Both integration items failed mechanical gates (`integration_mypy` and `integration_pytest`). The integrator assembled the modules but cross-cutting type checks and tests failed.
**Status:** Needs deeper forensics on the assembled workspace.

### 6. Qwen channel instability
**Root cause:** `channel_invoke_failed` on Qwen model with empty output. Occurred once in Attempt 4.
**Status:** Transient; no systemic pattern.

## Model-family Performance Comparison (Attempt 4)

| Role | Model | Family | Items | 1st-Att Pass | Overall Pass | Mean Duration |
|---|---|---|---|---|---|---|
| interface_architect | K2 | fireworks | 8 | 100% | 100% | 66.5s |
| test_author | K2 | fireworks | 7 | 100% | 100% | 85.9s |
| implementer | K2 | fireworks | 5 | 100% | 100% | 73.2s |
| cross_family_reviewer | Qwen | local-lms | 2 | 100% | 100% | 71.3s |
| frontier_judge (aggregate) | K2+Qwen | multi | 2 | 100% | 100% | — |
| integrator | K2 | fireworks | 2 | 0%* | 0% | 76.5s |

*Integrator outer gate first-pass rate 0/2; inner_json_shape 2/2.

## BC-145 Upstream Routing

**Exercised and found 3 bugs.** The upstream revision path (review/jury failure → create new implementation revision) had never been validated in prior golden runs because GR-034 had 0 review/jury failures. GR-035 was the first run to exercise this path at scale, and it revealed a chain of schema mismatches:
1. Missing `test_suite_ref` propagation
2. Missing workflow field declarations
3. Incorrect `work_item_ref` type for `upstream_revision_of`

All three fixes are committed. A clean re-run is needed to validate the fixed path.

## Claim-near-budget Behavior

5 items reached `attempt=3` (threshold). The runner hard-stopped them correctly. The wrapper tripped its `claim_near_budget ≥ 5` guardrail and killed the run. This is expected behavior per BC-139/BC-140 protocol. The high count (5) indicates systemic gate failures on the full DAG, primarily in the implementation and integration stages.

## Channel Health

| Channel | Model | Outcomes | Stability |
|---|---|---|---|
| opencode | K2 | 55+ items evaluated, 1 empty-output failure | Stable overall |
| opencode | Qwen | 6 items evaluated, 1 empty-output failure | Minor instability |

## Telemetry Integrity

| Check | Value | Status |
|---|---|---|
| unknown_gate_name_count | 0 | PASS |
| orphan_submit_count | 2 | FAIL |
| unmatched_gate_count | 0 | PASS |
| confounding_warning_count | 0 | PASS |
| verify_passed | False | FAIL |

The 2 orphan submits and `verify_passed: False` are artifacts of the gate process crash-looping on stuck review items (the gate submitted verdicts but the runner had already moved on, or vice versa).

## Artifacts Preserved

- Config: `.factory/golden-runs/golden-run-035-config.yaml`
- Logs: `.factory/logs/gr035/` (runner, gate, scheduler)
- Workspace: `/tmp/sf2-golden-035` (preserved via `--no-cleanup`)
- Isolated opencode DB: `/tmp/sf2-golden-gr035-opencode-data/`

## Lessons and Next Steps

1. **BC-145 upstream routing was unvalidated until GR-035.** Prior runs (GR-030 through GR-034) had zero review/jury failures, so the `ensure_upstream_revision` code path was dead. Full-DAG runs are needed to exercise failure-routing paths.
2. **Three bugs fixed, one re-run needed.** The upstream revision logic is now fixed at the scheduler and workflow levels. A fresh GR-035b (or GR-036) with the same config should validate whether the fixes hold.
3. **Integration stage failed 0/2 on full DAG.** Unlike GR-034 (2/2 on mini DAG), the full cert-watch integration items did not lock. Root cause unknown — requires workspace forensics.
4. **Wrapper idle detection is aggressive for full-DAG runs.** Model calls can exceed 6 minutes without log output, triggering the wrapper's idle timeout. Using `--monitor-interval 120` helps but does not eliminate the risk.
5. **FastAPI dependency gap in fixture.** The `fr04_web_api` interface spec requires `fastapi` but the fixture does not declare it. This causes mypy `import-not-found` failures.
6. **Claim-near-budget rate of 5/32 indicates the full DAG is harder than mini.** The full cert-watch fixture has more complex cross-module dependencies that push implementations past the 3-attempt budget.

**Recommendation:** Execute a fresh golden run (GR-036) with identical config after the three BC-145 fixes to confirm integration-lock generalizes. If integration still fails, focus on integrator prompt/workspace forensics before declaring Phase 5 exit.
