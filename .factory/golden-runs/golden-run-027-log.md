# Golden Run 027 — Dual-family jury (K2 + DeepSeek), cert-watch fixture, Phase 4

**Date:** 2026-05-14
**Config:** `golden-run-027-config.yaml`
**Channels:**
- opencode (fireworks-ai/accounts/fireworks/routers/kimi-k2p6-turbo) — interface_architect, test_author, implementer
- opencode (ollama-cloud/deepseek-v4-pro) — cross_family_reviewer
- opencode (fireworks + deepseek) — frontier_judge (dual jurors, jury_quorum=2)
**Fixture:** cert-watch (8 work-items: certificate_model, FR-01–FR-05, cert_chain_library, database_layer)
**Executed by:** OpenCode agent (agent-mediated via `scripts/agent_golden_run.py`)
**Wall clock:** ~65 minutes (21:58 → 23:03)

## Result

| Metric | Value | Target | Status |
|---|---|---|---|
| Total work items | 34 | — | — |
| Locked | 30 (88%) | ≥90% | **NEAR MISS** |
| Cannot proceed | 4 | — | Properly escalated |
| Stuck | 0 | ≤1 per 16-item DAG | **PASS** |
| Mean attempts to lock | 1.88 | ≤2.0 | **PASS** |
| First gate-evaluation pass rate | 88% (30/34) | ≥60% | **PASS** |
| Inner gate first-pass rate | 71% (17/24) | ≥60% | **PASS** |
| Unknown gate rate | 0.0% (0/64) | ≤10% | **PASS** |
| Deterministic gate rate | 100% (64/64) | ≥80% | **PASS** |

**Overall: SOME FAIL** (lock rate 88% vs 90% target — 4 items escalated to cannot_proceed)

## Per-stage detail

### Interface specs (8 items)
All 8 locked. 8/8 first-attempt gate pass. Inner gate: 4/8 first-pass (4 required retry for import/mypy issues, all recovered on retry 1).

### Test suites (8 items)
7/8 locked. 1 escalated to `cannot_proceed` after 3 attempts (inner gate loop exhausted — `test_suite_assertions` gate failure on first attempt, then inner gate retries consumed budget). 7/7 locked items passed on first gate evaluation.

### Implementations (6 items created, 5 locked)
5/6 locked. 1 escalated to `cannot_proceed` (implementation_pytest gate failed, exhausted retries). Inner gate first-pass: 5/6.

### Reviews (6 items created, 5 locked)
5/6 locked. 1 escalated to `cannot_proceed` (cross_family_review gate failure, exhausted retries). DeepSeek-v4-pro reviewer: 83% first-pass rate on `cross_family_review` gate.

### Jury (5 items created, 4 locked)
4/5 locked. 1 escalated to `cannot_proceed`. One `jury_disagree` case exercised (first time in golden run history!) — jurors disagreed on a review item, quorum not met on first attempt. 4/4 remaining passed `jury_quorum` on first attempt.

## Cannot-proceed items (4)

| Work item | Type | Attempt | Root cause |
|---|---|---|---|
| 16ee8dac | test_suite | 3 | Inner gate loop exhausted (assertion count mismatch) |
| 06a56e11 | jury | 3 | jury_disagree + subsequent budget exhaustion |
| 6065ba3d | implementation | 3 | implementation_pytest gate failure |
| 52fae369 | review | 3 | cross_family_review gate failure (DeepSeek reviewer) |

All 4 properly escalated via BC-139/BC-141 budget-limit escalation (claim → cannot_proceed transition). No infinite loops.

## Bugs found and fixed during GR-027 execution

### BC-141: opencode `run` subcommand returns empty output when cwd is not a project directory

**Root cause:** `opencode run` requires a project directory (with git repo and recognized project context) as cwd. When `subprocess_channel.py` used `cwd=str(outputs_dir)` (under `/tmp/sf2-golden-027/...`), opencode resolved to `projectID=global` and returned empty stdout/stderr with exit code 0.

**Fix:** Added `invocation_cwd: Path | None` to `FactoryConfig`. `SubprocessChannel.invoke()` uses `config.invocation_cwd` (if set) as the subprocess cwd, falling back to `outputs_dir`. Golden run configs set `invocation_cwd: /projects/software-factory-2`.

### BC-142: `agent_golden_run.py` launched processes from `/tmp` — broke opencode project context

**Root cause:** The BC-140 wrapper script launched runner/gate/scheduler with `cwd="/tmp"` for workspace isolation. But opencode needs a project directory. GR-026 worked only because GLM launched from repo root (the mistake that BC-140 was designed to prevent).

**Fix:** Changed `_launch_processes()` to use `cwd=REPO_ROOT` instead of `/tmp`. Also added git init in workspace for safety.

### BC-143: `claim_near_budget` released claim without escalating — zombie items cycle forever

**Root cause:** When `claim.attempt_number >= attempt_threshold`, the runner released the claim but didn't transition the item to a terminal state. The item returned to `new` state and was immediately reclaimed, creating an endless cycle of claim→release→claim→release. The BC-139 fix prevented infinite gate loops but created this runner-level loop.

**Fix:** `claim_near_budget` now transitions to `claim` (moving item to `in_progress`), then transitions to `cannot_proceed` (terminal state). This properly terminates budget-exhausted items.

### BC-144: `agent_golden_run.py` idle timeout too aggressive — killed working pipeline

**Root cause:** The monitor's idle detection (3 × interval = 90–180s) declared processes idle when the runner was silently processing a long model call. Each model call can take 2–5 minutes with inner gate retries.

**Fix:** Increased `max_idle_cycles` from 3 to 10 (10 × 60s = 10 minutes before declaring idle).

## Phase 4 validation milestones

1. **BC-139 fix validated** — no infinite retry loops on review/jury items. All budget-exhausted items properly escalated to `cannot_proceed`.
2. **`jury_disagree` exercised** — first golden run to exercise jury disagreement. One item had jurors disagree, quorum not met.
3. **DeepSeek-v4-pro as reviewer** — 83% first-pass rate on `cross_family_review`. Produced usable reviews for 5/6 items.
4. **Dual-family jury (K2 + DeepSeek)** — 4/5 jury items locked with `jury_quorum=2`. Disagreement exercised once.
5. **Full cert-watch DAG** — 8 fixture items, 34 pipeline items created, all 5 roles exercised.

## Telemetry

```
Pipeline Exit Criteria Summary

  Lock-within-budget rate:     88% (30/34)  FAIL [target: >=90%]
  Mean attempts to lock:        1.88  PASS [target: <=2.0]
  First gate-evaluation pass rate: 88% (30/34)  PASS [target: >=60%]
  Inner gate first-pass rate:    71% (17/24)  PASS [target: ≥60%]

  Stuck items:                 0  [target: <=1 per 16-item DAG]
  Unknown gate rate:            0.0% (0/64)  PASS [target: <=10%]
  Deterministic gate rate:      100% (64/64)  PASS [target: >=80%]

Per-(Role, Channel, Gate, PromptHash) Pass-Rate Report

  Role                    Channel       Family      Gate                              Hash  Items  1st-Att  Overall  MeanDur
  ----------------------  ------------  ----------  ----------------------------  --------  -----  -------  -------  -------
  cross_family_reviewer   opencode      ollama-cloud  cross_family_review           8fd8197b      6      83%      83%    17.9s
  frontier_judge          jury_aggregate  multi       jury_disagree                 cd9a1b57      1       0%       0%        —
  frontier_judge          jury_aggregate  multi       jury_quorum                   cd9a1b57      4     100%     100%        —
  implementer             opencode      fireworks   implementation                8b7f8075      6     100%     100%    66.0s
  implementer             opencode      fireworks   implementation_pytest         8b7f8075      1       0%       0%   221.4s
  implementer             opencode      fireworks   inner_mypy                           —      1       0%       0%   221.4s
  implementer             opencode      fireworks   inner_pytest                         —      6      83%     100%    70.5s
  interface_architect     opencode      fireworks   inner_pytest                         —      8      50%     100%    67.2s
  interface_architect     opencode      fireworks   interface_spec                91979699      8     100%     100%    61.9s
  test_author             opencode      fireworks   inner_pytest                         —      8     100%     100%    91.6s
  test_author             opencode      fireworks   inner_ruff                           —      1       0%       0%   199.6s
  test_author             opencode      fireworks   test_suite                    fcedb480      7     100%     100%    97.0s
  test_author             opencode      fireworks   test_suite_assertions         fcedb480      1       0%       0%    53.8s

  Overall: 58 items evaluated, 81% first-attempt pass, 90% overall pass
```

`telemetry --verify`: PASS (0 unknown gates, 0 orphans, 0 confounding warnings).

## Comparison with prior Phase 4 runs

| Run | Fixture | Jury config | Lock rate | Stuck | Cannot proceed | Jury disagree |
|---|---|---|---|---|---|---|
| GR-022 | cert-watch-mini (3 WI) | Single-family (K2) | 100% (15/15) | 0 | 0 | No |
| GR-023 | cert-watch-mini, broken impl | Single-family (K2) | 100% (15/15) | 0 | 0 | No |
| GR-025 | cert-watch-mini (3 WI) | Mixed (K2 + GLM) | 100% (16/16) | 0 | 0 | Yes |
| GR-026 | cert-watch-mini (3 WI) | Triple (K2+DS+GLM) | 92% (34/37) | 3 | 0 | No (loop) |
| **GR-027** | **cert-watch (8 WI)** | **Dual (K2+DS)** | **88% (30/34)** | **0** | **4** | **Yes** |

## Artifacts preserved

- **Config:** `golden-run-027-config.yaml` (includes `invocation_cwd` fix)
- **Workspace:** `.factory/gr027-workspace-backup/` (34 work items)
- **Logs:** `/tmp/gr027-runner.log`, `/tmp/gr027-gate.log`, `/tmp/gr027-scheduler.log`

## Lessons

1. **Opencode project context is a hard requirement.** The `opencode run` subcommand silently returns empty output when cwd is not a recognized project directory. This is a platform-level behavior, not a transient API issue. The `invocation_cwd` config field is now required for any golden run using the opencode channel.

2. **Budget-limit escalation must be terminal.** Releasing a claim without transitioning to a terminal state creates zombie items that cycle forever. The fix (claim → cannot_proceed) properly terminates items.

3. **Monitor idle timeout must account for model call duration.** A single model call + inner gate retries can take 5+ minutes. The idle timeout must be ≥10 minutes.

4. **`jury_disagree` is exercisable with dual-family jury.** K2 and DeepSeek can produce divergent opinions on review artifacts, triggering the disagreement path.

## Next steps

1. **Investigate the 4 cannot_proceed items.** Determine if the failures are systemic (model quality, prompt issues) or random (transient model errors).
2. **Re-run with K2-only reviewer** to isolate whether DeepSeek reviewer causes the review failures.
3. **Consider increasing attempt_threshold to 4** to give items more retries before escalation.
4. **File breadcrumb for `invocation_cwd` requirement** — document the opencode project context dependency.
