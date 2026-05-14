# Golden Run 026 — Triple jury (K2 + DeepSeek + GLM), cert-watch-mini fixture, Phase 4

**Date:** 2026-05-14
**Config:** `golden-run-026-config.yaml`
**Channels:** 
- opencode (fireworks-ai/accounts/fireworks/routers/kimi-k2p6-turbo) — interface_architect, test_author, implementer, cross_family_reviewer
- opencode (ollama-cloud/deepseek-v4-pro) — frontier_judge (juror 1)
- opencode (ollama-cloud/glm-5.1) — frontier_judge (juror 2)
- gemini-cli — frontier_judge (juror 3, unvalidated, disabled in runner registration)
**Fixture:** cert-watch-mini (3 work-items: certificate_model, FR-02, FR-03)
**Executed by:** GLM (agent-mediated, no human supervision)

## Result

| Metric | Value | Target | Status |
|---|---|---|---|
| Total work items | 37 | — | — |
| Locked | 34 (92%) | ≥90% | **PASS** |
| Stuck | 3 | ≤1 per 16-item DAG | **FAIL** |
| Cannot proceed | 0 | — | — |
| Interface spec lock rate | 8/8 (100%) | — | PASS |
| Test suite lock rate | 8/8 (100%) | — | PASS |
| Implementation lock rate | 8/8 (100%) | — | PASS |
| Review lock rate | 5/8 (62%) | — | FAIL* |
| Jury lock rate | 5/5 (100%) | — | PASS |
| Mean attempts to lock | 9.92 | ≤2.0 | **FAIL** |
| First gate-evaluation pass rate | 89% | ≥60% | PASS |
| Inner gate first-pass rate | 69% | ≥60% | PASS |
| Unknown gate rate | 0.0% | ≤10% | PASS |
| Deterministic gate rate | 100% | ≥80% | PASS |

*3 review items stuck in infinite retry loop (BC-139), consuming 548 gate evaluations without locking.

## Per-stage detail

### Interface specs (8 items)
All 8 interface_specs locked on first attempt. Inner gate: 6/8 passed on first try, 2 required retry (wrong_module_name import error, recovered on retry=1).

### Test suites (8 items)
All 8 test_suites locked on first attempt. Inner gate: 8/8 passed first try.

### Implementations (8 items)
All 8 implementations locked. 7 on first attempt, 1 required retry (`test_suite_assertions` gate failed on first attempt, passed on retry).

### Reviews (8 items)
- **5 locked** (b8e3703b, 0e981e18, 76b29525, ece47636, ef816ae2) — all passed `cross_family_review` gate on first attempt.
- **3 stuck** (1ec0bd0a, d5f15b78, dbdb908e) — `cross_family_review` gate failed on every attempt. Items looped to `new` state indefinitely because `cross_family_review` was not in `_ESCALATABLE_KINDS`.

### Jury (5 items)
All 5 jury items locked on first attempt. `jury_quorum` gate passed for all. No `jury_disagree` or `all_against` cases exercised.

## The BC-139 infinite retry loop

Three review work items entered an unbounded retry loop:

| Work item | Gate failures | Max attempt seen | Outcome |
|---|---|---|---|
| 1ec0bd0a | 188 | 378 | Stuck, manually killed |
| d5f15b78 | 187 | ~190 | Stuck, manually killed |
| dbdb908e | 173 | 347 | Stuck, manually killed |

**Cycle:** runner claims → invokes opencode → submits → gate fails `cross_family_review` → router sends to `new` → scheduler re-queues → runner re-claims → repeat.

**Root cause:** `cross_family_review` and `jury` diagnostic kinds fell through to `DiagnosticKind.GENERIC`, which is **not** in `_ESCALATABLE_KINDS`. The runner's `claim_near_budget` warning (line 192) was only a log line — it did not stop processing.

**Impact:**
- 548 total `cross_family_review` gate evaluations wasted
- ~32M K2 tokens consumed (contained by fast-fail dynamics and possible rate limiting)
- ~370 opencode sessions created in `~/.local/share/opencode/opencode.db`
- Wall clock: ~90 minutes of loop before manual kill
- Mean attempts to lock inflated to 9.92 (target ≤2.0)

**Post-run fix:** BC-139 resolved in the same session:
1. Added `DiagnosticKind.CROSS_FAMILY_REVIEW` and `DiagnosticKind.JURY`
2. Added both to `_ESCALATABLE_KINDS` (escalate to `cannot_proceed` at threshold)
3. Runner `claim_near_budget` is now a hard stop (releases claim + skips)

## Telemetry

```
Pipeline Exit Criteria Summary

  Lock-within-budget rate:     92% (34/37)  PASS [target: >=90%]
  Mean attempts to lock:        9.92  FAIL [target: <=2.0]
  First gate-evaluation pass rate: 89% (34/38)  PASS [target: >=60%]
  Inner gate first-pass rate:    69% (18/26)  PASS [target: >=60%]

  Stuck items:                 3  [target: <=1 per 16-item DAG]
  Unknown gate rate:            0.0% (0/367)  PASS [target: <=10%]
  Deterministic gate rate:      100% (367/367)  PASS [target: >=80%]

  Overall: SOME FAIL

Per-(Role, Channel, Gate, PromptHash) Pass-Rate Report

  Role                    Channel       Family      Gate                              Hash  Items  1st-Att  Overall  MeanDur
  ----------------------  ------------  ----------  ----------------------------  --------  -----  -------  -------  -------
  cross_family_reviewer   opencode      fireworks   cross_family_review           8fd8197b      8      62%      62%    11.6s
  frontier_judge          jury_aggregate  multi       jury_quorum                   cd9a1b57      5     100%     100%        —
  implementer             opencode      fireworks   implementation                8b7f8075      8     100%     100%    46.2s
  implementer             opencode      fireworks   inner_mypy                           —      2       0%       0%    84.4s
  implementer             opencode      fireworks   inner_pytest                         —      8     100%     100%    46.2s
  interface_architect     opencode      fireworks   inner_pytest                         —      8      25%      62%   172.9s
  interface_architect     opencode      fireworks   interface_spec                91979699      8     100%     100%   154.6s
  test_author             opencode      fireworks   inner_pytest                         —      8     100%     100%    62.3s
  test_author             opencode      fireworks   test_suite                    fcedb480      8     100%     100%    64.7s
  test_author             opencode      fireworks   test_suite_assertions         fcedb480      1       0%       0%    43.1s
  unknown                 unknown       unknown     cross_family_review                  —      1       0%       0%        —

  Overall: 65 items evaluated, 80% first-attempt pass, 85% overall pass
```

`telemetry --verify`: PASS (0 unknown gates, 0 orphans, 0 confounding warnings).

**Note:** The telemetry "unknown" entry for `cross_family_review` is from the looping items where the gate event could not be matched to a submit event because the runner skipped resume due to prior gate fail.

## Phase 4 exit criteria assessment

Per `spec.md` §10, Phase 4 exit criteria (inherited from Phase 3 where applicable):

| Criterion | Target | Actual | Status |
|---|---|---|---|
| Lock-within-budget rate | ≥90% | 92% | **PASS** |
| Mean attempts to lock | ≤2.0 | 9.92 | **FAIL** (inflated by loop) |
| First-attempt mechanical pass rate | ≥60% | 89% | PASS |
| Stuck items | ≤1 per 16 WI | 3 per 37 WI | **FAIL** |
| Unknown gate rate | ≤10% | 0.0% | PASS |
| Deterministic gate rate | ≥80% | 100% | PASS |

**Verdict:** The run fails on `mean_attempts` and `stuck_items` due to BC-139. Without the infinite loop, the run would likely meet all criteria:
- 34/34 non-looping items locked (100%)
- Mean attempts on non-looping items ≈ 1.2
- 0 stuck items

## Multi-family jury validation

This was the first run to attempt a **triple-family jury**:
- K2 (fireworks) — validated in GR-022/023/024/025
- DeepSeek (ollama-cloud) — juror 1
- GLM (ollama-cloud/glm-5.1) — juror 2
- Gemini CLI was configured but disabled (unvalidated adapter)

The 5 jury items that reached the frontier_judge all passed `jury_quorum` on first attempt. However:
- No `jury_disagree` case was exercised (all 5 passed cleanly)
- The `[all_against]` tag validated in GR-025 was not triggered here
- DeepSeek and GLM jurors did not get a chance to produce divergent opinions because the review items feeding them were either stuck (3) or passed (5)

## Agent execution mistakes (BC-140)

1. **Context pollution:** GLM launched processes from repo root (`/projects/software-factory-2`), causing every opencode invocation to be associated with the repo directory.
2. **No loop recognition:** GLM did not notice attempt counts climbing to 300+ and did not cross-reference with known issues.
3. **Session deletion:** GLM deleted the working session when asked to clean junk sessions from the opencode DB.
4. **No post-run commit:** GLM left artifacts uncommitted (config, breadcrumbs, worklog).

These led to BC-140 (agent-mediated run protocol) and the `agent_golden_run.py` wrapper script.

## Artifacts preserved

- **Config:** `golden-run-026-config.yaml` (committed)
- **Workspace:** `.factory/gr026-workspace-backup/` (37 work items, 119MB) — preserved locally, not in git
- **Logs:** `/tmp/gr026-runner.log`, `/tmp/gr026-gate.log`, `/tmp/gr026-scheduler.log`
- **Breadcrumb:** BC-139 (resolved), BC-140 (proposed)

## Comparison with prior Phase 4 runs

| Run | Jury config | Review lock rate | Jury lock rate | Notes |
|---|---|---|---|---|
| GR-022 | Single-family (K2 only) | 8/8 (100%) | 5/5 (100%) | First Phase 4 run, all roles exercised |
| GR-023 | Single-family (K2 only) | 5/5 (100%) | 3/3 (100%) | Broken-impl fixture, inner gate telemetry visible |
| GR-024 | GLM isolated | Did not reach review | Did not reach jury | GLM implementer empty output (13/16 failures) |
| GR-025 | Mixed-family (K2 + GLM) | 5/5 (100%) | 3/3 (100%) | `jury_disagree` exercised, `[all_against]` validated |
| GR-026 | Triple-family (K2 + DeepSeek + GLM) | 5/8 (62%) | 5/5 (100%) | BC-139 infinite loop on 3 review items |

## Next steps

1. **Re-run with BC-139 fix:** Execute GR-027 with `agent_golden_run.py` wrapper to validate that review/jury failures now escalate instead of looping.
2. **Exercise `jury_disagree`:** Use a fixture with intentional defects to force jury disagreement and validate multi-family divergence handling.
3. **Validate DeepSeek/GLM as jurors:** GR-026 showed they can pass jury_quorum, but did not exercise disagreement scenarios.

## Lessons

1. **Agent-mediated runs need guardrails.** Unattended execution without monitoring loops is dangerous. The `agent_golden_run.py` wrapper provides those guardrails.
2. **New gate kinds need escalation coverage.** Any new `DiagnosticKind` must be added to `_ESCALATABLE_KINDS` if it represents a retryable failure. The default `GENERIC` fallback is a trap.
3. **Fast-fail dynamics can mask token burn.** 32M tokens on ~370 invocations means most invocations were quick rejects, but the session DB still pays the price.
