# Golden Run 029 — Full cert-watch DAG through Phase 5 (integration), K2-only, scheduler crash

**Date:** 2026-05-15
**Config:** `golden-run-029-config.yaml`
**Channels:**
- opencode (fireworks-ai/accounts/fireworks/routers/kimi-k2p6-turbo) — all roles (single-family)
**Fixture:** cert-watch full (8 work-items: certificate_model, FR-01–FR-05, cert_chain_library, database_layer)
**Executed by:** OpenCode agent (agent-mediated via `scripts/agent_golden_run.py`)
**Wall clock:** ~65 minutes
**Note:** Three prior launch attempts aborted:
1. DeepSeek model unavailable ("Model not found" / "Unexpected server error")
2. GLM-5.1 model unavailable (same errors — provider removed from opencode config)
3. Single-family K2-only with `jury_quorum=2` — `jury_disagree` cycling killed by `gate_fail_jury` guardrail

Final run used K2-only with `jury_quorum=1`.

## Result

| Metric | Value | Target | Status |
|---|---|---|---|
| Total work items | 24 | — | — |
| Locked | 21 (88%) | ≥90% | **NEAR MISS** |
| Cannot proceed | 3 | — | Properly escalated |
| Stuck | 0 | ≤1 per 16-item DAG | **PASS** |
| Mean attempts to lock | 2.17 | ≤2.0 | **FAIL** |
| First gate-evaluation pass rate | 88% (21/24) | ≥60% | **PASS** |
| Inner gate first-pass rate | 62% (13/21) | ≥60% | **PASS** |
| Unknown gate rate | 0.0% (0/52) | ≤10% | **PASS** |
| Deterministic gate rate | 100% (52/52) | ≥80% | **PASS** |

**Overall: SOME FAIL**

## Per-stage detail

### Interface specs (8 items)
8/8 locked. First-attempt gate pass: 8/8 (100%). Inner gate first-pass: 3/8 (38%) — 5 items required retry on `inner_pytest` (import smoke check). All recovered on retry.

### Test suites (7 items)
6/7 locked, 1 cannot_proceed (`gate=implementation_mypy` timeout at 641.7s — likely cross-module import failure). First-attempt gate pass: 6/7 (86%). Inner gate first-pass: 5/7 (71%) — 2 items failed `inner_test_collect` on first attempt but recovered on retry.

### Implementations (3 items visible in telemetry)
3/3 locked. First-attempt gate pass: 3/3 (100%). Inner gate: 3/3 first-pass on `inner_pytest`.

### Reviews (2 items)
2/2 locked. First-attempt gate pass: 2/2 (100%).

### Jury (1 item)
1/1 locked. Single-family K2-only with `jury_quorum=1` — unanimous pass. `jury_disagree` path **not exercised**.

### Integration (1 item)
1/1 locked. `integration_import` first-attempt pass.

### Outcome verification (0 items)
**Not reached.** The scheduler crashed (exit code 1) before creating `outcome_verification` downstream items. The 3 `cannot_proceed` items and the scheduler crash prevented the chain from reaching this stage.

## Infrastructure issues

### Model availability regression
Both `ollama-cloud/deepseek-v4-pro` and `zai-coding-plan/glm-5.1` returned "Model not found" / "Unexpected server error" on every invocation. This is a provider-side regression from GR-027 (2026-05-14) when DeepSeek was available. The `zai-coding-plan` provider may have been removed from the opencode configuration entirely.

### Scheduler crash (exit code 1)
`PID=632460 (scheduler)` exited with code 1 during the run. Root cause unknown — logs were auto-cleaned before inspection. The runner and gate continued running, but no new downstream work items were created after the scheduler died. This blocked the `integration → outcome_verification` handoff and prevented the full Phase 5 chain from completing.

### Jury disagreement cycling with quorum=2 on single-family
When both `frontier_judge` jurors use the same K2 model, `jury_quorum=2` produces systematic disagreement (the same model invoked twice with identical prompts yields divergent outputs). This triggered the `gate_fail_jury` guardrail at ≥3 occurrences, aborting the run. Setting `jury_quorum=1` resolved this but means the disagreement path is unexercised.

## Telemetry

- **Contract Complaint Telemetry (BC-120):** 0 contract-shaped rationales.
- **Routing Hint Telemetry (BC-145):** 0 outcome_verification gate_fail events.
- **Verify:** passed (0 orphan submits, 0 unmatched gates, 0 unknown gate names).

## Phase exit criteria assessment

This run is **not a valid Phase 5 exit candidate** due to:
1. Scheduler crash preventing outcome_verification stage
2. Single-family jury (disagreement path not exercised)
3. Lock rate 88% (near-miss, same as GR-027)
4. Mean attempts 2.17 (above ≤2.0 target)

## Artifacts preserved

- Config: `golden-run-029-config.yaml`
- Logs: `/tmp/gr029-{runner,gate,scheduler}.log` — **auto-cleaned**, not preserved
- Workspace: `/tmp/sf2-golden-029` — **auto-cleaned**, not preserved
- Isolated opencode DB: `/tmp/sf2-golden-gr029-opencode-data` — **auto-cleaned**, not preserved

**No workspace backup exists for forensics.**

## Lessons / next steps

1. **Model availability is unstable.** DeepSeek and GLM were both available during GR-024/025/027 but dead today. K2 (fireworks) is the only validated reliable model. Need a provider-health pre-flight check before every run, or a fallback model list.
2. **Scheduler crash needs investigation.** The exit code 1 suggests an unhandled exception. The auto-cleanup removed the logs. Next run should use `--no-cleanup` to preserve the scheduler log for post-mortem.
3. **Single-family jury with quorum=2 is a trap.** Same model invoked twice will disagree stochastically. For single-family runs, `jury_quorum=1` is required. Multi-family jury requires at least one working alternate model.
4. **Outcome verification stage unexercised.** The cert-watch full DAG is large enough to reach this stage if the scheduler survives. A smaller fixture (cert-watch-mini with 5 items) or a direct scheduler integration test would validate the `integration → outcome_verification` handoff independently.
5. **Inner gate first-pass on test_author `collect` is weak.** 2/7 test suites failed `pytest --collect-only` on first attempt. The prompt may need stronger guidance on import resolution or test structure.
