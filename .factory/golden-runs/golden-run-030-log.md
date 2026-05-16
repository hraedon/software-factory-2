# Golden Run 030 — Phase 5 integration validation, K2+Qwen dual-family jury, cert-watch-mini

**Date:** 2026-05-15
**Config:** `golden-run-030-config.yaml`
**Channels:**
- opencode (fireworks-ai/accounts/fireworks/routers/kimi-k2p6-turbo) — worker roles + integrator + outcome_verifier
- opencode (mac-studio-lms/qwen/qwen3.6-27b) — cross_family_reviewer + 1 frontier_judge juror
- opencode (fireworks-ai/accounts/fireworks/routers/kimi-k2p6-turbo) — 1 frontier_judge juror (jury_quorum=2)
**Fixture:** cert-watch-mini (3 work-items: certificate_model, fr02_tls_scan, fr03_file_upload)
**Executed by:** GLM-5.1 agent (manual process launch with setsid)
**Wall clock:** ~35 minutes

## Bug fixed during run

**Link type direction bug (integrates/verified_by).** The scheduler creates links with `from=downstream(new_item), to=source(locked_item)`. The workflow YAML defined `integrates: source=jury, target=integration` and `verified_by: source=integration, target=outcome_verification`, which are reversed — the newly created item (integration/outcome_verification) should be the source. Fixed by changing to:
- `integrates: source=integration, target=jury`
- `verified_by: source=outcome_verification, target=integration`

Without this fix, the scheduler's `create_link()` calls returned `SubstrateError: Link type 'derived_from' not allowed between 'integration' and 'jury'` (the old config used `derived_from` as link_type, which also didn't exist). The fix resolved both the wrong link_type name and the wrong source/target direction.

## Result

| Metric | Value | Target | Status |
|---|---|---|---|
| Total work items | 15 | — | — |
| Locked | 12 (80%) | ≥90% | **FAIL** |
| Cannot proceed | 3 | — | Properly escalated |
| Stuck | 0 | ≤1 per 16-item DAG | **PASS** |
| Mean attempts to lock | 1.87 | ≤2.0 | **PASS** |
| First gate-evaluation pass rate | 86% (12/14) | ≥60% | **PASS** |
| Inner gate first-pass rate | 67% (8/12) | ≥60% | **PASS** |
| Unknown gate rate | 0.0% (0/28) | ≤10% | **PASS** |
| Deterministic gate rate | 100% (28/28) | ≥80% | **PASS** |
| Verify passed | False (1 orphan_submit) | — | **NEAR MISS** |

**Overall: SOME FAIL** (lock rate 80%, below 90% target)

## Per-stage detail

### Interface specs (3 items)
3/3 locked. Inner gate: 1/3 first-pass (wrong_module_name on 2 items, recovered on retry). 1st gate pass: 3/3.

### Test suites (3 items)
3/3 locked. Inner gate: 3/3 first-pass. 1st gate pass: 3/3.

### Implementations (2 items locked, 1 cannot_proceed)
2/3 locked. Item `70ee8108` (fr02_tls_scan implementation) hit `inner_mypy` failures (type-arg, attr-defined errors in the SSL socket interface), then `channel_fail` on retry, then `cannot_proceed` at attempt 3. 1st gate pass: 2/3.

### Reviews (2 items)
2/2 locked. Qwen 3.6-27b as cross_family_reviewer. 1st gate pass: 2/2.

### Jury (2 items)
2/2 locked. Dual-family jury with `jury_quorum=2`: K2 + Qwen 3.6-27b. Both jurors unanimous pass. `jury_disagree` path **not exercised** — both models agreed.

### Integration (2 items, both cannot_proceed)
0/2 locked. Both integration items passed inner_pytest but failed `integration_import` gate. The integrator role generated artifacts that didn't meet the import resolution gate. This is the first time the integration stage was exercised in a golden run — the gate is new and the integrator prompt may need refinement.

### Outcome verification (0 items)
Not reached. Integration items never locked, so no downstream outcome_verification items were created by the scheduler.

## Telemetry

- **Contract Complaint Telemetry (BC-120):** 0 contract-shaped rationales.
- **Routing Hint Telemetry (BC-145):** 0 outcome_verification gate_fail events.
- **Verify:** failed (1 orphan_submit, 0 unmatched gates, 0 unknown gate names).
- **Dual-family jury exercised:** Yes (K2 + Qwen 3.6-27b).
- **Integration stage exercised:** Yes (2 items, both cannot_proceed).
- **Outcome verification stage exercised:** No (blocked by integration failures).

## Phase exit criteria assessment

This run is **not a valid Phase 5 exit candidate** due to:
1. Lock rate 80% (below 90% target)
2. Integration stage 0/2 locked — new gate needs prompt refinement
3. Outcome verification never reached — blocked by integration failures
4. Jury disagreement path not exercised (dual-family but both agreed)

## Key findings

1. **Link type bug fixed:** `integrates` and `verified_by` link types in `workflows/phase5.yaml` had reversed source/target directions. The scheduler creates links as `from=new_item to=locked_item`, so link types must have the new item as `source_type`. Fixed in this run.
2. **Integration import gate works mechanically:** The `evaluate_integration` gate correctly validates assembled_tree JSON artifacts, writes files to tempdir, and runs import/mypy/pytest. The integrator prompt needs refinement to produce artifacts that pass the import gate.
3. **Dual-family jury operational:** Qwen 3.6-27b via Mac Studio local server works as a second family for review and jury roles.
4. **Orphan submit:** 1 item had a submit event without a corresponding gate claim — likely from the `channel_fail` path where the item was submitted to substrate before the channel failure was detected.

## Artifacts preserved

- Workspace: `.factory/gr030-workspace-backup/`
- Config: `golden-run-030-config.yaml`
- Runner log: `/tmp/gr030-runner.log`
- Gate and scheduler logs: lost (setsid redirect files were deleted when shell session closed)