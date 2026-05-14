# Software Factory v2 — Worklog

Reverse-chronological session log. Prepend new entries above existing ones.

---

## 2026-05-14 — Session 32: GR-027 execution; opencode project-context bug; budget-limit escalation fix

**Invocation:** OpenCode (fireworks-ai/accounts/fireworks/routers/kimi-k2p6-turbo)

**Focus:** Execute GR-027 (full cert-watch, Phase 4, dual-family jury K2+DeepSeek). Discovered and fixed 4 bugs along the way.

### GR-027 Result

- **30/34 locked (88%)** — near-miss on 90% target
- **0 stuck items** — BC-139 fix validated
- **4 cannot_proceed** — properly escalated via budget-limit
- **jury_disagree exercised** — first time in golden run history
- Wall clock: ~65 minutes

### Bugs discovered and fixed

1. **opencode project-context bug (BC-141):** `opencode run` returns empty output when cwd is not a recognized project directory. Root cause: `subprocess_channel.py:93` used `cwd=str(outputs_dir)` which was under `/tmp/`. Fix: added `invocation_cwd` to `FactoryConfig`, subprocess channel uses it for cwd.

2. **agent_golden_run.py cwd issue (BC-142):** Wrapper script launched processes with `cwd="/tmp"` for isolation. Fix: changed to `cwd=REPO_ROOT` since workspace isolation is via config `workspace_root`, not process cwd.

3. **Budget-limit zombie cycling (BC-143):** `claim_near_budget` released claim without transitioning to terminal state, creating endless claim→release→claim→release cycle. Fix: claim → cannot_proceed transition sequence.

4. **Monitor idle timeout too short (BC-144):** 3 × interval (90-180s) killed working pipeline. Fix: increased to 10 × interval (10 minutes).

### Files modified

- `src/factory/config.py` — added `invocation_cwd: Path | None`
- `src/factory/subprocess_channel.py` — use `invocation_cwd` for subprocess cwd
- `src/factory/runner.py` — budget-limit escalation: claim → cannot_proceed
- `scripts/agent_golden_run.py` — cwd=REPO_ROOT, git init, longer idle timeout, higher claim_near_budget threshold
- `golden-run-027-config.yaml` — added `invocation_cwd`, absolute `hmac_key_path`

### Tests

688 pass, 0 lint errors (src/). Pre-existing lint errors in scripts/ (analysis utilities) not addressed.

---

## 2026-05-14 — Session 31: GR-026 post-mortem; GLM session-deletion mistake

**Invocation:** OpenCode (fireworks-ai/accounts/fireworks/routers/kimi-k2p6-turbo) — **replacement session** after GLM cleanup deleted the prior working session.

**Focus:** Assess repo damage from GR-026 (GLM-attempted Phase 4 golden run), commit the artifacts GLM produced, document the mistakes, and file BC-140 for agent-mediated run process.

### Background

GLM attempted to execute GR-026 (full cert-watch, Phase 4, triple jury: K2 + DeepSeek + GLM) earlier today. The run encountered the infinite retry loop bug (BC-139) where review gate failures cycle to `new` forever because `cross_family_review` is not in `_ESCALATABLE_KINDS`. Two review work items (`1ec0bd0a`, `dbdb908e`) looped to 340+ and 174+ attempts respectively before the principal killed the processes.

### Mistakes made by GLM

1. **Ran the pipeline in the factory repo context.** GLM launched the runner/gate/scheduler while `cwd=/projects/software-factory-2`. Every opencode subprocess invocation was associated with this directory, polluting `~/.local/share/opencode/opencode.db` with hundreds of junk sessions.

2. **Did not recognize the infinite retry loop.** The loop consumed unbounded model budget and session entries. GLM should have noticed the attempt count climbing and cross-referenced with known issues.

3. **Deleted the working session during cleanup.** When asked to clean the junk sessions from the opencode DB, GLM used a broad deletion that wiped the current working session as well. The session history from the prior working session was lost. A new session had to be started.

4. **Did not produce a worklog entry or commit artifacts.** GLM left `golden-run-026-config.yaml`, `breadcrumbs/139-review-jury-infinite-retry-loop.md`, and the breadcrumbs README modification uncommitted.

### Artifacts committed in this session

- `golden-run-026-config.yaml` — GR-026 config (triple jury, K2 + DeepSeek + GLM, quorum=2)
- `breadcrumbs/139-review-jury-infinite-retry-loop.md` — BC-139: critical bug report documenting the infinite retry loop
- `breadcrumbs/README.md` — index update for BC-139
- `.factory/worklog.md` — this entry

### New breadcrumb filed

- **BC-140:** "No standard invocation process for agent-mediated factory runs" — high severity. The absence of a documented protocol for how agents should execute golden runs leads to context pollution, unbounded budget burn, and data loss. See `breadcrumbs/140-agent-mediated-run-protocol.md`.

### Breadcrumbs status

- **Open:** 139 (critical), 138 (medium), 120 (medium, deferred).
- **New in this session:** 140 (high, proposed).

### BC-139 resolution

**Implemented in this session.** Two-part fix:

1. **Router (`src/factory/router.py`):** Added `DiagnosticKind.CROSS_FAMILY_REVIEW` and `DiagnosticKind.JURY`. Updated `_classify_diagnostic()` to recognize `cross_family_review` and `jury` diagnostic kinds from `GateResult`. Added both to `_PHASE2_DISPATCH` (route to `new` below threshold). Added both to `_ESCALATABLE_KINDS` so that at `attempt_number >= attempt_threshold`, the router escalates to `cannot_proceed_seam` instead of cycling to `new` forever.

2. **Runner (`src/factory/runner.py`):** `claim_near_budget` warning is now a **hard stop**. When `claim.attempt_number >= config.attempt_threshold`, the runner releases the claim and `continue`s to the next work item. This prevents model budget burn on items that the gate will eventually escalate, acting as a belt-and-suspenders safety net.

**Tests:** 8 new tests added (2 classification + 2 escalation for each kind). Total tests: 670 pass, 13 skipped, 0 lint errors.

### Breadcrumbs status (post-fix)

- **Open:** 138 (medium), 120 (medium, deferred), 140 (high, proposed).
- **Resolved in this session:** 139 (critical → resolved).

### Test results

Repo unaffected by GR-026: 670 tests pass, 13 skipped, 0 lint errors. Damage confined to `/tmp/sf2-golden-026` (119MB workspace artifacts), `.ruff_cache` (bloat from hundreds of gate runs), and opencode session DB (prior session lost).

---

## 2026-05-14 — Session 30: Housekeeping — Opus feedback resolution

**Invocation:** OpenCode (fireworks-ai/accounts/fireworks/routers/kimi-k2p6-turbo)

**Focus:** Resolve loose ends identified by Opus in adversarial review: backfill missing golden-run logs, move resolved breadcrumb, update AGENTS.md stale counts.

### Items completed

1. **Golden-run log backfill (023/024/025):** Created standalone `golden-run-NNN-log.md` files for GR-023 (broken-impl fixture, K2-only, 5/5 locked), GR-024 (GLM-5.1 isolated validation, implementer empty-output failure), and GR-025 (mixed-family K2 + GLM jury, jury_disagree exercised, quorum=0%). Restores run-log auditability without reverting to `git log`.

2. **BC-136 moved to `breadcrumbs/resolved/`:** `136-channel-failover-backup.md` relocated; README.md index updated. BC-136 was implemented in commit `224aaff` (Session 29) but remained in open breadcrumbs due to oversight.

3. **AGENTS.md updated:**
   - Test count updated: 620 → 650 (Session 29 added 13 channel-failover tests)
   - Open breadcrumb count: 2 → 1 (BC-136 resolved). Now reads: "1 open breadcrumb (0 critical, 0 high, 1 medium, 0 low) + 1 proposed (deferred to Phase 4) + 18 RFCs."
   - Breadcrumb status in README.md already correct.

### Items already correct (no change needed)

- **Spec.md Phase 4 exit criteria:** Already present in §10 (lines 310–329) from a prior edit. Telemetry header already reads "Pipeline Exit Criteria Summary" in commit `48ad1fe` (BC-133 resolution).
- **Telemetry header:** "Pipeline Exit Criteria Summary" is correct and phase-agnostic.

### Breadcrumbs status

- **Open:** 138 (medium), 120 (high, proposed).
- **Resolved in this session:** 136 (high).

### Test results: 650 pass, 13 skipped, 0 lint errors

---


## 2026-05-14 — Session 29: Gemini capability probe; BC-136/138 triage

**Invocation:** OpenCode (fireworks-ai/accounts/fireworks/routers/kimi-k2p6-turbo)

**Focus:** Run BC-137 flawed-spec capability probe against Gemini (Flash + Pro) to complete the model evaluation matrix. Validate Node.js fix for Gemini CLI. Triage open breadcrumbs.

### Gemini capability probe results

The Gemini CLI Node.js issue (v18 regex flags) was resolved by prepending `~/.nvm/versions/node/v24.15.0/bin` to PATH, matching the `GeminiCLIChannel._extra_env()` implementation.

| Role | Flash (s) | Pro (s) | Notes |
|---|---|---|---|
| interface_architect | 38.1 | 72.6 | Pro fixed the `bool` flaw in `consume` → `float \| None` |
| test_author | 64.6 | 33.9 | Both produced pytest suites |
| implementer | 160.5 | 76.3 | Pro significantly faster; both returned runnable code |
| cross_family_reviewer | 17.1 | 19.3 | Both flagged 5/5 planted defects (passed=false) |
| frontier_judge | 21.8 | 27.0 | Both returned correct `passed: false` with rationale |

**Key finding:** Gemini 2.5 Pro passes all 5 roles on the flawed-spec probe. It is operationally viable for every role in the pipeline, including code-generation roles where Qwen 3.6-27b timed out (BC-138). This makes Gemini the sixth validated model+provider combination (alongside K2-Fireworks, K2-Ollama, GLM-z.ai, GLM-Ollama, DeepSeek-Ollama).

### Breadcrumb assessment

- **BC-136 (channel failover):** Remains the highest-impact open item. No code changes this session; queued for implementation.
- **BC-138 (Qwen timeout):** Recommendation confirmed — restrict Qwen to review/judge roles only. Gemini Pro is a viable alternative for code-gen roles if a third family is needed.
- **BC-120 (interface amendment):** Deferred to post-BC-136.

### Housekeeping

- `spec.md` status updated: Phase 3 → Phase 4.
- `AGENTS.md` uncommitted Node.js note committed.
- New script: `scripts/capability_probe_gemini.py` (Node 24 PATH fix, dual-model support).

### Test results: 637 pass, 13 skipped, 0 lint errors

---

## 2026-05-13 — Session 28: v1+K2p6 control experiment on cert-watch

**Invocation:** Opus 4.7 (remote-control session, no code changes to sf2)

**Focus:** Disentangle "v2 architecture vs. K2 model improvement" as explanations for v2 clearing cert-watch where v1 could not. Ran v1 with the same Kimi K2p6 model v2 uses, against the same cert-watch spec.

### Setup

- Target: `/projects/software-factory/projects/cert-watch-11` (reset with `factory reset --hard --reset-git`).
- Spec edits: `provider: opencode → openai`, `model: k2p5-turbo → k2p6-turbo` on all three roles (architect, implementer, reviewer). Base URL `https://api.fireworks.ai/inference/v1`.
- v1's `openai` provider (`factory/agents/providers/openai_loop.py`) hits Fireworks directly via OpenAI-compatible API. No code changes needed.
- API key (Firepass-scoped) authenticated cleanly against K2p6.

### Result

**v1+K2p6 hard-failed at Stage 2.5 (Skeleton Architect / BC-294) after three self-correction attempts.** Never reached agent fan-out, never wrote feature code.

All three violations were the same class (E5) on the same file: the skeleton plan declared exports (`get_config_dep`, `get_scanner_service`, `get_certificate_parser_service`) from `src/cert_watch_11/web/deps_base.py` that the model then failed to define as top-level bindings when emitting the file. Plan-vs-emission inconsistency. K2p6 could not reconcile its own plan against its own code in 3 attempts.

Artifacts preserved at `/projects/software-factory/projects/cert-watch-11/.factory/`:
- `worktrees/skeleton-architect/.factory/skeleton-plan-violations.yaml`
- `observability/factory.log`

### Interpretation

The failure mechanism is specific and load-bearing. v1's Skeleton Architect stage asks one model invocation to (a) declare a structural plan and (b) emit files that conform to it, then validates them against each other. K2 cannot reliably satisfy that contract — it contradicts its own earlier structural commitments within a single long output.

v2's pipeline shape has no equivalent stage. `interface_architect` writes the interface as a separate work item; `implementer` writes code against that interface in a fresh context, mechanically gated. The "model forgot what it said five minutes ago" failure mode is structurally impossible in v2.

This narrows the v2 claim from the vague "better orchestration" to the specific **"stage decomposition is small enough that the model can't contradict itself across stages."** That is a defensible architectural win, grounded in evidence. It also recontextualizes the v2 jury/review stages: they're not just catching defects — they're checking a model whose upstream stages have already prevented the most common self-contradiction failure mode.

### What this does NOT prove

- We don't know whether v1+K2p6 would have failed downstream too (merge collisions, gate-not-enforced bugs). We stopped at the first failure rather than forcing past it.
- We don't know whether a single-invocation plan-and-emit contract is fundamentally infeasible for K2, or whether v1's specific validator strictness is the proximate cause. v2 just avoids the question.
- This is a single fixture (cert-watch) and a single model (K2p6). Other models with stronger long-context self-consistency might survive v1's skeleton stage. K2 cannot.

### Next steps

None directly from this experiment — the result is recorded. The pre-existing Phase 4 validation work (synthetic bad-impl fixture for the reviewer, multi-family jury GR, jury disagreement path) remains the actual blocker for declaring Phase 4 done.

---

## 2026-05-12 — Session 26: BC-125 resolved; AGENTS.md and docs refreshed

**Invocation:** GLM-5.1

**Focus:** Resolve BC-125, update stale documentation, assess BC-120.

### Breadcrumbs resolved (1)

- **BC-125 (medium):** `populate_work_items.py --workflow` now defaults to `None` instead of `"phase2"`. When `--config` is provided and `--workflow` is not explicitly set, workflow is inferred from `config.workflow_version` via `{1: "phase1", 2: "phase2", 3: "phase3"}` mapping. Also fixed summary line printing `args.project` instead of resolved `project` variable. 2 new tests.

### Documentation updated

- **AGENTS.md:** test count 405→477, golden run count 14→19, breadcrumb count 5→4, next concrete step updated, golden run examples updated to GR-019, workflow count 2→3, `--workflow inferred from config` noted.
- **breadcrumbs/README.md:** BC-125 moved from Open to Resolved.

### Test results: 477 pass, 0 lint errors

---

## 2026-05-12 — Session 25: BC-122/123/124 throughput improvements; GR-019 validation

**Invocation:** OpenCode (fireworks-ai/accounts/fireworks/routers/kimi-k2p6-turbo)

**Focus:** Implement three breadcrumbs targeting the 0% first-attempt pass rate observed in GR-015. Validate with GR-019.

### Breadcrumbs implemented (3)

- **BC-122 (high):** Prompt pre-flight checklists. Added "Pre-flight verification" sections to all three role prompt templates (`interface_architect.md`, `test_author.md`, `implementer.md`) with itemized checklists for the model to self-verify before outputting.

- **BC-124 (medium):** Selective ruff rule set for inner gate. Added `INNER_GATE_RUFF_SELECT`, `INNER_GATE_RUFF_IGNORE`, `INNER_GATE_RUFF_UNSAFE_FIXES` to `constants.py`. Inner gate now uses `--select E,F,I,N,W,UP,RUF --ignore E501` matching `pyproject.toml`. Outer gate unchanged (full ruleset).

- **BC-123 (medium):** Inner gate auto-fix-back. `_run_ruff_fast` now: (1) runs targeted unsafe fix for F841 only, (2) runs safe fixes for all selected rules, (3) formats, (4) final verify. When content changes, saves model's raw output as `.<name>.orig` before writing back the fixed version.

### Fixes during review

Three issues caught during pre-flight review, all fixed:

1. **Inner gate ruleset diverged from pyproject.toml** — widened from `E,W,F,I` to `E,F,I,N,W,UP,RUF` to eliminate possibility of inner-gate-pass → outer-gate-fail.
2. **`--unsafe-fixes` was a blanket flag** — replaced with targeted `--unsafe-fixes --select F841` pass for unused variable removal only.
3. **Auto-fix overwrote model's raw output** — added conditional `.orig` backup; only written when content actually changes.

### Golden Run 019 — K2-only, cert-watch full DAG

Wall clock: ~65 min (03:13 – 04:18 UTC). One item stuck on channel timeout.

**Inner gate results (clean signal):**

| Metric | GR-015 | GR-019 |
|---|---|---|
| Inner gate first-attempt pass (retry=0) | 0/24 (0%) | 7/11 (64%) |
| Ruff failures | 8/8 interface specs | **0** |
| Lock rate | 24/24 (100%) | 15/16 (94%) |
| Remaining failure modes | ruff, import, mypy, pytest | import, mypy, pytest only |

- 1 item stuck: `d75ba24b` (cert_chain_library implementation) — channel timeout on every invocation. Model capability issue, not pipeline issue.
- **Zero ruff failures across the entire run.** Ruff eliminated as a failure mode.
- Outer gate telemetry shows 0% first-attempt due to contaminated attempt counters from multiple partial runs. Inner gate data is the clean signal.

### Breadcrumbs opened (1)

- **BC-125:** `populate_work_items.py --config` doesn't infer `--workflow` from config YAML, causing work items to be created with wrong workflow version. Led to GR-019 first attempt finding zero work items.

### Test results: 474 pass, 13 skip, 0 lint errors, 0 audit findings

---

## 2026-05-12 — Session 24: Golden runs 015–018; BC-121 critical regression; model capability evaluation

**Invocation:** OpenCode (fireworks-ai/accounts/fireworks/routers/kimi-k2p6-turbo)

**Focus:** Execute GR-015/017/018 to validate Phase 3 multi-channel dispatch and compare model-family capability per role.

### Golden Run 015 — COMPLETE (K2-only, cert-watch full DAG)

Wall clock: ~60 min (22:10 – 23:10 UTC).

| Stage | Total | Locked | Cannot proceed | Lock rate |
|---|---|---|---|---|
| interface_spec | 8 | 8 | 0 | 100% |
| test_suite | 8 | 8 | 0 | 100% |
| implementation | 8 | 8 | 0 | 100% |
| **Total** | **24** | **24** | **0** | **100%** |

Telemetry verify: passed (0 unknown gates, 0 orphans, 0 unmatched gates).

**Key finding:** 0% first-attempt pass rate across all roles. Every work item required inner-gate retry=1 (or retry=2) to pass. This is a prompt-shaped problem, not a model-shaped one — the prompts do not teach the model to self-check before returning output.

### Critical regression discovered: BC-121

During GR-015 execution, outer gate failed every test_suite and implementation with "pytest not installed" / "mypy not installed" / "ruff not installed".

Root cause: BC-115 moved gate tooling into a separate `.venv-gate`, but `gate_process.py` and `runner.py` still called `ensure_project_venv()` which returns the project-venv python (now gate-tool-free after `_clean_stale_project_venv` runs).

Fix committed:
- `ensure_gate_venv()` made public; installs both `_GATE_TOOLS` and project `requirements.txt`
- Hash includes gate-tools hash + requirements hash
- `gate_process.py` and `runner.py` both use `ensure_gate_venv()` for gate operations
- GR-015 re-run with fixed code: 100% lock rate, 24/24 items.

### Golden Run 017 — INCOMPLETE (GLM implementer binding)

Config: interface_architect→K2, test_author→K2, implementer→GLM-5.1

Result: **GLM implementer failed catastrophically.**
- 7/8 interface_specs locked (K2, normal behavior)
- 3/8 test_suites locked (K2, normal behavior)
- **1 implementation stuck at attempt 16** with repeated channel failures:
  - "Could not extract artifact from opencode output"
  - "Empty output from opencode"
- Nanny timed out at 60 min.

**Assessment:** GLM-5.1 via zai-coding-plan/opencode is **not viable for implementer role** on the cert-watch workload. Smoke tests (simple prompts) passed, but real implementation prompts exceed its reliable generation capacity. Likely long-context degradation or provider-side chat-bias tuning.

### Golden Run 018 — INCOMPLETE (DeepSeek implementer binding)

Config: interface_architect→K2, test_author→K2, implementer→DeepSeek-v4-pro

Result: **DeepSeek implementer partially functional but weaker than K2.**
- 6/8 interface_specs locked
- 2/3 test_suites locked
- 1 implementation locked
- 1 implementation stuck at attempt 4 with mypy type errors (wrong cryptography API, missing type annotations)
- Nanny timed out at 60 min.

**Assessment:** DeepSeek makes substantive coding errors (type mismatches, wrong library APIs) that K2 fixes on retry=1. DeepSeek is viable for interface_architect/test_author, but **K2 remains the best implementer** on current evidence.

### Comparative model capability table (cert-watch full DAG)

| Role | K2 pass rate | GLM pass rate | DeepSeek pass rate |
|---|---|---|---|
| interface_architect | 100% (8/8) | 100% (7/7) | 100% (6/6) |
| test_author | 100% (8/8) | 100% (2/2) | 100% (2/2) |
| **implementer** | **100% (8/8)** | **0%** (stuck, empty output) | **~50%** (1 locked, 1 stuck on type errors) |

### Breadcrumbs opened (4)

- **BC-121:** Gate process and runner use project venv instead of gate venv for gate tooling (critical, implemented)
- **BC-122:** Prompt pre-flight checklist to improve first-attempt pass rate (high, proposed)
- **BC-123:** Inner gate auto-fix: copy ruff-corrected artifacts back instead of retrying (medium, proposed)
- **BC-124:** Selective ruff rule set for model output — relax non-critical rules (medium, proposed)

### Breadcrumbs resolved (2)

- BC-107: GR-015 config switched to validated K2-only binding
- BC-117: Scheduler pagination test added

### Fixes committed

- `golden-run-015-config.yaml` — corrected K2 model string (`fireworks-ai/accounts/fireworks/routers/kimi-k2p6-turbo`)
- `src/factory/config.py` — `FactoryConfig.phase3()` default model string corrected
- `src/factory/venv.py` — `ensure_gate_venv()` public, installs requirements too
- `src/factory/gate_process.py` — uses `ensure_gate_venv()`
- `src/factory/runner.py` — uses `ensure_gate_venv()` for pre-gate deps
- `scripts/golden_run_nanny.py` — fixed `PROCESSES` tuple unpacking bug
- `tests/test_phase3.py` — updated model string assertion
- `golden-run-017-config.yaml` — new (K2/K2/GLM)
- `golden-run-018-config.yaml` — new (K2/K2/DeepSeek)

### Test results: 469 pass, 13 skip, 0 lint errors, 0 audit findings

---

## 2026-05-11 — Session 23: Close 20 breadcrumbs + 4 self-identified fixes

**Invocation:** OpenCode (glm-5.1)

**Focus:** Resolve all actionable breadcrumbs from adversarial review, then clean up self-identified gaps.

### Breadcrumbs resolved (20)

BC-081, 096–116: arbitrary directory deletion guard, credential redaction fix, env footgun fix, SubprocessChannel env merge, output extraction robustness, JSON extraction via raw_decode, scheduler pagination loop, quarantine collision safety, gate size limits, ast-parse DoS (subsumed by BC-104), golden-run nanny, circuit breaker backoff, adversarial output tests, path traversal guards, FAMILY_OLLAMA dead code removal, hasattr removal, ruff tempdir copy, venv gate isolation, SyntaxError in assertion count.

### Self-identified fixes (4)

1. Circuit breaker constants moved from module-level to `FactoryConfig.channel_backoff_base_seconds` / `.channel_backoff_max_attempts` (BC-056 convention).
2. `GATE_MAX_ARTIFACT_SIZE_BYTES` consolidated into `MAX_ARTIFACT_SIZE_BYTES` — was a maintenance trap.
3. `golden_run_nanny.py` — removed dead `for _, log_file_handle in []: pass`; added proper `log_files` tracking with `close()` in all exit paths.
4. `venv.py` — `_gate_tools_hash()` uses stable input string; `_clean_stale_project_venv` removes gate tools from old project venvs with `.gate_tools_removed` marker.

### Breadcrumbs opened (3)

- BC-117: Scheduler pagination has no integration test (needs mocked paginated substrate)
- BC-118: golden_run_nanny.py lacks timeout and progress reporting
- BC-119: Venv gate tool hash won't detect version changes

### Test results: 469 pass, 13 skip, 0 lint errors, 0 audit findings

### Files created/modified

- `src/factory/config.py` — added `channel_backoff_base_seconds`, `channel_backoff_max_attempts`
- `src/factory/constants.py` — removed `GATE_MAX_ARTIFACT_SIZE_BYTES` and `FAMILY_OLLAMA`
- `src/factory/credentials.py` — redaction clamp, env footgun fix
- `src/factory/dep_resolution.py` — `_safe_artifact_path` path traversal guard
- `src/factory/gate.py` — size guard, ruff tempdir, SyntaxError in assertion count, import consolidation
- `src/factory/gate_process.py` — path traversal guard in `_resolve_ref_artifact`
- `src/factory/output_extraction.py` — last-python-block preference, raw_decode JSON extraction
- `src/factory/pre_gate.py` — ruff tempdir copy
- `src/factory/runner.py` — circuit breaker with config values, hasattr removal
- `src/factory/scheduler.py` — pagination loop using `page.has_more`/`page.cursor`
- `src/factory/subprocess_channel.py` — explicit os.environ merge
- `src/factory/venv.py` — gate venv isolation, stale project venv cleanup
- `src/factory/workspace.py` — subsecond timestamp, collision counter
- `populate_work_items.py` — `_validate_workspace_root_for_reset` guard
- `scripts/golden_run_nanny.py` — new, replaces raw &/wait
- `Makefile` — golden-run target uses nanny
- `tests/test_credentials.py` — new, redaction + env footgun tests
- `tests/test_output_extraction_adversarial.py` — new, adversarial parsing tests
- `tests/test_path_traversal.py` — new, path traversal tests
- `tests/test_populate_reset_guard.py` — new, reset guard tests
- `tests/test_gate_assertion_count.py` — SyntaxError test added
- `tests/test_opencode_channel.py` — ollama-cloud family updated
- 20 breadcrumb files moved to `breadcrumbs/resolved/`
- 3 new breadcrumb files opened
- `breadcrumbs/README.md` — index updated

---

## 2026-05-11 — Session 22: BC-084 resolved; GR-014 executed

**Invocation:** OpenCode (glm-5.1)

**Focus:** Resolve BC-084 (module name derivation fragility) and validate with Golden Run 014.

### BC-084 resolved

Root cause: `_extract_module_name_from_spec()` derived module names from model-generated spec titles, producing mangled names like `certificate_model__cert_parser_` from "Certificate Model (cert-parser)".

Fix: Added `CUSTOM_FIELD_MODULE_NAME` constant. `populate_work_items.py` now stores `label.removeprefix("wi_")` as `module_name` on every interface_spec work item. `resolve_dep_artifacts()` reads `module_name` from custom fields first, falling back to the regex. Both workflow YAMLs (phase1.yaml, phase2.yaml) declare the new field. 3 new tests.

### GR-014 results (cert-watch full fixture, kimi-k2p6-turbo via Fireworks, opencode channel)

Wall clock: ~33 min (05:37 – 06:10 UTC).

| Stage | Total | Locked | Cannot proceed | Lock rate |
|---|---|---|---|---|
| interface_spec | 8 | 8 | 0 | 100% |
| test_suite | 8 | 6 | 2 | 75% |
| implementation | 6 | 6 | 0 | 100% |
| **Total** | **22** | **20** | **2** | **91%** |

Test suite lock rate doubled from 37.5% (GR-013) to 75%. The 2 remaining escalations are model quality issues (invalid dataclass, ImportError in generated code), not pipeline bugs.

### Telemetry verify: passed (0 unknown gates, 0 orphans)

### Files created/modified

- `src/factory/constants.py` — added `CUSTOM_FIELD_MODULE_NAME`
- `src/factory/dep_resolution.py` — reads `module_name` custom field first, falls back to spec-title regex
- `populate_work_items.py` — stores `module_name` on work items; removed duplicate `import re`
- `tests/test_cross_module_deps.py` — 3 new tests for module_name resolution
- `workflows/phase1.yaml`, `workflows/phase2.yaml` — declared `module_name` custom field on all work item types
- `breadcrumbs/084-module-name-derivation-fragile.md` → `breadcrumbs/resolved/` — closed
- `breadcrumbs/README.md` — updated index
- `golden-run-014-config.yaml` — GR-014 config
- `golden-run-014-log.md` — full analysis

## 2026-05-11 — Session 21: GR-013 executed; BC-077 resolved; BC-084 filed

**Invocation:** OpenCode (glm-5.1)

**Focus:** Execute Golden Run 013 against full cert-watch DAG (8 specs) to validate BC-077 (dep ordering fix). Diagnose new failures.

### GR-013 results (cert-watch full fixture, kimi-k2p6-turbo via Fireworks, opencode channel)

Wall clock: ~30 min (03:29 – 04:01 UTC).

| Stage | Total | Locked | Cannot proceed | Lock rate |
|---|---|---|---|---|
| interface_spec | 8 | 8 | 0 | 100% |
| test_suite | 8 | 3 | 5 | 37.5% |
| implementation | 3 | 3 | 0 | 100% |
| **Total** | **19** | **14** | **5** | **73%** |

### BC-077 validated

Root dependency `certificate_model` was the FIRST interface_spec claimed and locked (03:29:31), compared to GR-012 where it was the LAST. All 8 interface_specs locked in the first ~10 minutes. The scheduler correctly deferred downstream creation until deps were ready.

### BC-084 filed: module name mangling

Root cause of 5 test_suite escalations: `_extract_module_name_from_spec()` derives module names from model-generated spec titles via regex. "Certificate Model (cert-parser)" → `certificate_model__cert_parser_` instead of `certificate_model`. The gate copies deps under mangled names; test code imports the correct name → ImportError at collection.

Only `database_layer` ("Database Layer") matched its fixture name by coincidence. The 3 passing test_suites (certificate_model, fr04_alerts, fr05_scheduler) either had no deps or their interfaces didn't import from dependency modules.

### Other validations

- BC-075/BC-079/BC-082: inner gate caught mypy errors and retried correctly
- BC-046: resume guard worked
- Telemetry verify: passed (0 unknown gates, 0 orphans)

### Files created/modified

- `golden-run-013-config.yaml` — config
- `golden-run-013-log.md` — full analysis with module name derivation table
- `breadcrumbs/084-module-name-derivation-fragile.md` — new BC (high)
- `breadcrumbs/077-runner-no-dep-ordering.md` → `breadcrumbs/resolved/077-runner-no-dep-ordering.md` — closed
- `breadcrumbs/README.md` — updated index
- `AGENTS.md` — added golden run execution instructions

**Invocation:** OpenCode (glm-5.1)

**Focus:** Incorporate Opus/GLM feedback for cert-watch fixture; execute Golden Run 012 against updated fixture.

### Fixture changes (cert-watch)

1. **AC enforcement for runtime dep calls:**
   - `wi_fr02_tls_scan.md` AC-04: `ScannedEntry.leaf` must equal `parse_certificate(handshake_der)` — forces calling parse, not literal construction
   - `wi_fr04_alerts.md` AC-02: thresholds computed against `Certificate.days_until_expiry()` on a real instance — forces loading certificate_model
   - `wi_database_layer.md` AC-02: `add(cert)` must persist `cert.fingerprint_sha256` from a `parse_certificate`-created instance

2. **New `wi_cert_chain_library.md`** — non-FR utility module with 4 ACs (`extract_chain`, `validate_chain_order`, `split_leaf_intermediates`, `deduplicate_chain`). No FR mapping. Validates pipeline tolerance for non-FR work-items.

3. **fr04_alerts wired to `certificate_model` + `database_layer`** — 3rd diamond consumer of certificate_model root.

4. **fr02/fr03 also depend on `cert_chain_library`** — adds library dep chain.

5. **BC-076 breadcrumb updated** to reflect new dependency graph (8 work-units, 3 diamond consumers, non-FR module, AC enforcement).

### GR-012 results (cert-watch full fixture, Kimi via Fireworks, opencode channel)

Wall clock: 26.3 min.

| Stage | Total | Locked | Cannot proceed |
|---|---|---|---|
| interface_spec | 8 | 8 (100%) | 0 |
| test_suite | 8 | 3 (37.5%) | 5 (62.5%) |
| implementation | 3 | 3 (100%) | 0 |
| **Total** | **19** | **14 (73%)** | **5 (26%)** |

**5 escalated test_suites (all `test_suite_collect` ImportError):**
- cert_chain_library, database_layer, fr02_tls_scan, fr04_alerts, fr01_dashboard

**Root cause:** `certificate_model` (root dependency) was the last interface_spec to be processed. All downstream test_suites failed because their dependency's interface spec wasn't locked when the gate tried to resolve imports. The runner claims items in database query order without respecting dependency topology.

**BC-077 filed:** Runner processes interface_specs without dependency ordering. Proposed fix: scheduler should defer test_suite creation until all dependency interface_specs are locked (Option B).

**Non-FR module finding:** `cert_chain_library` was handled correctly by all pipeline components. Failed for the same root cause as other modules (missing certificate_model), not because of its non-FR status.

**AC enforcement:** Could not be validated — tests failed at collection before assertions could run. Requires BC-077 fix first.

---

## 2026-05-10 — Session 19: BC-076 implemented — dep resolution prefers locked implementations

**Invocation:** OpenCode (glm-5.1)

**Focus:** Implement BC-076 fix: when resolving dependency references, prefer the locked implementation's `.py` artifact over the interface_spec's `.pyi` stub for runtime use, while keeping the spec's `.pyi` for mypy type checking.

**Changes:**

1. **New module `src/factory/dep_resolution.py`** — Centralized dependency resolution:
   - `DepArtifact` dataclass with `module_name`, `impl_path`, `spec_path`, `is_stub_only`
   - `resolve_dep_artifacts()` — resolves each dep ref, finding locked implementations via `_find_locked_impl()` (queries substrate for locked implementations matching the spec's `interface_ref`)
   - `resolve_dep_refs_for_gate()` — returns `list[tuple[str, Path]]` of primary artifact paths (impl .py preferred over spec .pyi)
   - `resolve_dep_refs_for_gate_rich()` — returns `list[tuple[str, Path, Path | None]]` with both impl and spec paths
   - `resolve_dep_refs_for_context()` — returns `(contents_dict, stub_only_list)` for prompt injection

2. **`src/factory/context.py`** — Updated `PromptContext` with `stub_only_deps: list[str]`; `_resolve_dependency_contents` now returns `(dict, list)` tuple; `render_prompt()` adds `## stub_only_dependencies` warning section; `_serialize_bundle` includes `stub_only_deps` in context hash

3. **`src/factory/gate_process.py`** — `_resolve_dependency_refs()` now returns `tuple[list[tuple[str, Path]], list[tuple[str, Path]] | None]` (primary paths + spec paths); delegates to `resolve_dep_artifacts` for impl-preference logic

4. **`src/factory/pre_gate.py`** — `PreGateDeps` gains `dep_spec_paths` field; `copy_dependency_pyis()` gains `dependency_spec_paths` parameter; when impl exists, writes `.py` from impl and `.pyi` from spec; when stub-only, writes same content as both (preserving backward compatibility)

5. **`src/factory/gate.py`** — `evaluate_test_suite()` and `evaluate_implementation()` gain `dependency_spec_paths` parameter; propagated through `_run_pytest_collect`, `_run_mypy`, `_run_pytest`

6. **`src/factory/runner.py`** — `_resolve_pre_gate_deps` unpacks the new tuple; `PreGateDeps` now includes `dep_spec_paths`; `PromptContext` construction includes `stub_only_deps`

7. **`tests/fixtures/cert-watch/`** — Full 7-work-unit fixture with diamond deps, multi-hop chains

8. **Tests:** All 374 pass, lint clean, audit clean. Existing test `PromptContext` constructions updated with `stub_only_deps=[]`.

**Key design choice (per Opus):** Option 1 (find locked impl artifact) is the architecturally honest fix. Option 2 (prompt guard) is the fallback for stub-only deps. Both are implemented.

**Scheduler note:** No scheduler change needed. The scheduler already propagates `dependency_refs` verbatim. The dep resolution finds locked implementations at query time. For parallel channels (Phase 3+), the scheduler should respect dep-impl ordering — but that's a Phase 3+ concern.

---

## 2026-05-10 — Session 18: GR-011 complete; BC-076 filed; cert-watch full fixture created

**Invocation:** OpenCode (glm-5.1)

**Focus:** Execute GR-011 to validate BC-074/075 fixes; diagnose FR-03 failure; create expanded cert-watch fixture; file BC-076.

**GR-011 result (cert-watch-mini, kimi-k2p6-turbo via Fireworks):**
- 9 work items: 8 locked (89%), 1 escalated (11%)
- Interface specs: 3/3 (100%), Test suites: 3/3 (100%), Implementations: 2/3 (67%)
- FR-03 file_upload escalated to `cannot_proceed` — inner gate pytest failures on `test_upload_certificate_valid_pem_returns_uploaded_entry`
- Wall clock: ~21 min. Telemetry verification passed.

**Root cause diagnosis (principal-identified):**
- FR-03 test calls `parse_certificate(der)` from `certificate_model`, but the gate copies the `.pyi` stub as the runtime `.py` dep. Stub bodies are `...` (Ellipsis), so `parse_certificate(der)` returns `Ellipsis`, failing the `isinstance` check.
- FR-02 passed because its test constructs `Certificate(...)` directly — never calling the dep's functions at runtime.
- This is a pipeline gap, not a model quality issue. BC-076 filed at severity=high.

**BC-076: Dependency .pyi stub bodies are Ellipsis — gate copies stub as runtime dep.**
- `copy_dependency_pyis()` copies `.pyi` content into both `.py` and `.pyi` files for dependency modules. For interface specs, `.pyi` bodies are `...`, causing runtime failures.
- Three options proposed: (1) add implementation work-items to fixtures so dep has real `.py`, (2) prompt guard for test_author, (3) gate auto-mocking (rejected).
- Option 1 is the honest fix; option 2 is complementary.

**New fixture: `/tests/fixtures/cert-watch/`**
- 7 work-units with full dependency graph matching v1 cert-watch:
  - certificate_model (no deps) — foundation
  - database_layer ← certificate_model
  - fr01_dashboard ← database_layer
  - fr02_tls_scan ← certificate_model, database_layer (diamond dep)
  - fr03_upload ← certificate_model, database_layer (diamond dep)
  - fr04_alerts ← database_layer
  - fr05_scheduler ← fr02_tls_scan, fr04_alerts (multi-hop chain)
- Exercises: independent foundation, single-dep, diamond deps, multi-hop chains.
- Retains `tests/fixtures/cert-watch-mini/` as the 3-spec quick-validation fixture.

**Files created/modified:**
- `golden-run-011-config.yaml` — config
- `golden-run-011-log.md` — full analysis
- `breadcrumbs/076-dep-stub-as-runtime-pipeline-gap.md` — new BC
- `breadcrumbs/README.md` — updated index
- `tests/fixtures/cert-watch/` — 7 spec files + requirements.txt

---

## 2026-05-10 — Session 17: GR-011 validation of BC-074/075 fixes

**Invocation:** OpenCode (glm-5.1)

**Focus:** Execute golden run 011 to validate BC-072 (cross-module imports), BC-074 (dependency context injection), BC-075 (inner gate loop with pytest).

**GR-011 result:**
- 9 work items: 8 locked (89%), 1 escalated (11%)
- Interface specs: 3/3 locked (100%)
- Test suites: 3/3 locked (100%)
- Implementations: 2/3 locked (67%), 1/3 escalated (FR-03 file_upload)
- Wall clock: ~21 minutes
- Telemetry verification: passed (0 unknown gates, 0 orphans, 0 confounding)

**Inner gate loop (BC-075) validated:**
- Implementation `4191c68d`: inner gate caught RUF059 on retry 0, passed on retry 1
- Implementation `c47c6e90`: inner gate caught pytest failures on retries 0 and 1, exhausted max_retries=2, submitted anyway; outer gate then also failed; item ultimately escalated to cannot_proceed
- Implementation `3387c000`: inner gate passed first try, no retries needed

**BC-074 dependency context validated:** Cross-module test_suites and implementations resolved imports correctly. No ModuleNotFoundError in any gate.

**BC-039 lint autofix validated:** Inner gate ruff check caught and autofixed RUF059 (unused unpacked variable).

**BC-046 resume guard validated:** `skipping_resume_due_to_prior_gate_fail` correctly logged for `c47c6e90` on attempt 3.

**BC-037 escalation routing validated:** `c47c6e90` escalated to cannot_proceed after attempt_threshold=3.

**Remaining issue:** FR-03 `test_upload_certificate_valid_pem_returns_uploaded_entry` consistently fails pytest across multiple implementation attempts. This appears to be a model quality issue (model can't correctly implement the certificate-aware upload function) rather than a pipeline bug.

**Artifacts:**
- `golden-run-011-config.yaml` — config
- `golden-run-011-log.md` — full run log and analysis

---

## 2026-05-09 — Session 16 (continued): GR006a complete — Phase 2 PAUSE decision

**GR006a result:**
- 7 work-items total: 5 locked (71%), 2 escalated (29%)
- Interface spec: 3/3 locked (100%)
- Test suite: 1/3 locked (33%), 2 escalated (67%)
- Implementation: 1/1 locked (100%) — but only 1 created because 2 test_suites escalated
- **Implementation lock rate: 33%** (below 40% threshold)

**Criteria test results:**
- `test_gr006a_meets_phase2_exit_threshold`: **FAIL** (0.33 < 0.70)
- `test_gr006a_produces_no_unknown_gate_names`: **PASS**
- `test_gr006a_cross_module_imports_resolve`: **FAIL**
- `test_gr006a_telemetry_verify_passes`: **PASS**

**Phase 2 decision per plan §2.3:** `test_gr006a_meets_phase2_exit_threshold` fails (< 40% impl) → **PAUSE Phase 3; root-cause.**

**Root cause identified:** Cross-module import resolution in gate temp directory.
Both FR-02 and FR-03 test_suites import `Certificate` from `certificate_model` (a separate interface_spec dependency). The gate's `_run_pytest_collect` only copies the direct `interface.pyi` → `interface.py` into the temp directory. It does NOT copy `certificate_model.pyi`, so pytest collection fails with `ModuleNotFoundError`.

**Fix required before Phase 3:**
1. Scheduler must propagate full dependency chain into work-item custom_fields
2. Gate must copy ALL dependency `.pyi` files into pytest/mypy temp directories
3. OR: test_author prompt must be instructed not to import from cross-module dependencies

**Artifacts produced:**
- `golden-run-006a-log.md` — full run log and analysis
- `tests/fixtures/golden-run-006a/telemetry.json` — results for criteria tests
- `tests/fixtures/golden-run-006a/artifacts.json` — root cause documentation

---

## 2026-05-09 — Session 16: Opus plan execution — Window A, 1.2–1.5, C1, C6; GR006a kicked off

**Invocation:** OpenCode (kimi-k2p6-turbo)

**Focus:** Execute `plans/phase2-close-and-phase3-prep.md` (claude-opus-4-7 authored).

**Window A — Bundled telemetry refactor (+30 tests, 329 pass):**
- A1: Consumer-level event schemas (`src/factory/event_schemas.py`) with round-trip + replay fixture tests
- A2: Prompt template hash in ActorMetadata; telemetry groups by hash; confounding-warning on multi-hash groups
- A3: Attempt-level latency tracking (`duration_seconds` in SubmitPayload/ChannelFailPayload); mean/median duration in telemetry table; `per_channel_timeout` config
- A4: `python -m factory.telemetry --verify` data-quality gate (unknown gate names, orphan submits, unmatched gates, confounding)
- A5: Bundle gate clean (`make check` passes)

**Window 1.2 — Per-project venv helper:**
- `src/factory/venv.py` with `ensure_project_venv()`; uv-preferred; hash-based cache; 4 tests

**Window 1.3 — Behavioral gate stub:**
- `src/factory/behavioral_gate.py` stub; skip-when-empty, NotImplementedError when scenarios present
- Playwright fixture (`tests/fixtures/broken_fastapi/app.py`)
- Skip-marked test is Phase-5 accountability

**Window 1.4 — Assertion-counting gate:**
- `_check_assertion_count()` after collect-only in `evaluate_test_suite()`
- Fails on zero-assertion test functions or total assertions < function count
- `DiagnosticKind.TEST_NO_ASSERTIONS` routes to `test_author`
- 5 tests

**Window 1.5 — GR006a fixtures + criteria tests:**
- `tests/fixtures/cert-watch-mini/` with 3 interface specs (certificate_model, FR-02 TLS scan, FR-03 file upload)
- `golden-run-006a-config.yaml` (claude-code, `use_project_venv: true`)
- `tests/test_gr006a_criteria.py` with 4 skip-when-absent criteria tests

**Window C1 — BC-060 channel protocol cleanup:**
- Removed dead `inputs_dir` from `Channel.invoke()`, all adapters, all call sites, all tests
- Added `tests/test_channel_protocol_no_dead_params.py` introspection test

**Window C6 — `make golden-run` automation:**
- Makefile `golden-run` target chains populate → runner/gate/scheduler → report → telemetry --verify
- `populate_work_items.py` gains `--config` and `--fixtures` flags

**GR006a execution kicked off:**
- `make golden-run CONFIG=golden-run-006a-config.yaml FIXTURES=tests/fixtures/cert-watch-mini` running in background
- 3 work-items populated (wi_certificate_model, wi_fr02_tls_scan, wi_fr03_file_upload)
- Pre-built venv at `/tmp/sf2-gr006a/.venv` with `cryptography>=42.0`
- 2 interface_specs already `locked` after ~10 minutes; 1 test_suite `in_progress`
- Run PID logged at `/tmp/gr006a-run.pid`; log at `/tmp/gr006a-run.log`

**Breadcrumbs status:**
- BC-060 moved to resolved (channel protocol cleanup)
- BC-061 (channel composition refactor) — remaining Window C item
- All other open breadcrumbs unchanged

**Commits:**
- `9428978` — Window A telemetry bundle + debate resolution + plans
- `57099f3` — Windows 1.2–1.5 (venv, behavioral stub, assertion gate, GR006a fixtures)
- `0e28695` — Window C1 (BC-060 channel cleanup)
- `31ac9f8` — Window C6 (make golden-run automation)

---

## 2026-05-09 — Session 15: Execute Golden Runs 004 and 005

**Invocation:** OpenCode (deepseek-v4-pro)

**Focus:** Execute two golden runs:
- GR004: Validate BC-039 (auto-format + implementer prompt), BC-046 (resume-on-gate-fail guard), telemetry reporter (claude-code channel, Sonnet)
- GR005: Validate BC-040 (OpenCodeChannel adapter) with Kimi k2.6 via Fireworks AI (opencode channel)

**GR004 result: 42/46 items locked (91%), 4 escalated (9%).**
- 15/15 interface_specs (100%), 15/15 test_suites (100%), 12/15 implementations (80%)
- Massive improvement over GR003 (17% → 80% impl pass rate). BC-039 + BC-046 validated.

**GR005 result: 43/46 items locked (93%), 2 escalated (4%), 1 in_progress.**
- 15/15 interface_specs (100%), 15/15 test_suites (100%), 13/15 implementations (87%)
- First non-Anthropic golden run. Kimi k2.6 via opencode channel. Only 1 impl escalation (vs 3 for Sonnet).
- BC-040 validated end-to-end. Family derivation "fireworks" correct. OpenCodeChannel works for real providers.
- Kimi slower than Sonnet (~52 min vs ~31 min) but produces better lint-passing code.

**Telemetry:** family-per-invocation telemetry working for both channels. Same "unknown" gate name + 0% first-attempt bug in both runs — event-matching logic needs refinement.

**Configs:** `golden-run-004-config.yaml`, `golden-run-005-config.yaml`.

**Wall clock:** GR004 ~31 min, GR005 ~52 min. 293 unit tests clean.

**Post-run artifacts:** `golden-run-004-log.md`, `golden-run-005-log.md`.

---

## 2026-05-08 — Session 14: Resolve BC-057, BC-033, BC-031

**Invocation:** OpenCode (glm-5.1)

**Focus:** Resolve three open breadcrumbs: dead code CI, telemetry reporter, main() extraction.

**BC-057 — Dead code audit + CI enforcement:**
- Removed dead code: `KIND_TO_ROLE` dict (router.py:43), `work_root()` function (workspace.py:31), redundant `invocation_family` reassignment (claude_code_channel.py:58-61)
- Added `vulture>=2.0` to dev dependencies in pyproject.toml
- Created `make audit` target running `vulture src/factory/ tests/ .vulture_whitelist.py --min-confidence 80`
- Added `audit` to `make check` (now: lint + audit + test)
- Whitelist at `.vulture_whitelist.py` for signal handler `frame` params (false positive)

**BC-033 — Telemetry reporter skeleton:**
- Created `src/factory/telemetry.py` with:
  - `collect_gate_attempts(sub, config)` — reads work items and events, pairs submit→gate events to extract worker role/channel/family
  - `compute_pass_rates(attempts)` — groups by (role, channel, family, gate_name), computes first-attempt and overall pass rates per unique work item
  - `format_pass_rate_table(rows)` — outputs markdown table with header, per-row stats, and summary line
  - `run_telemetry_report(config)` — main entry point
  - `_main(argv)` / `main()` — CLI wrapper
- Registered `factory-report` CLI entry point in pyproject.toml
- 12 tests in `tests/test_telemetry.py`

**BC-031 — Extract main() into testable _main():**
- Refactored `runner.py`, `gate_process.py`, `scheduler.py`, `telemetry.py` to use `_main(argv)` pattern
- Each `main()` is now a one-line wrapper: `_main()`
- 6 tests in `tests/test_main_entry.py` verifying arg parsing and delegation

**Test results:** 282 passed, 1 skipped, 0 failed. 0 lint errors. 0 dead code findings.

**Breadcrumbs moved to resolved:** BC-057, BC-033, BC-031.

---

## 2026-05-08 — Session 13: Fix BC-041 — _create_channel factory crash on default config

**Invocation:** Claude Code

**Focus:** Fix a startup-crash bug discovered while reviewing BC-040 implementation.

**Bug:** `runner.py:_create_channel()` iterated over `config.roles` to build a set of distinct channel names. The default config includes `mechanical_gate` with `channel="code"` (deterministic evaluation, not a model channel), producing a set of size 2 (`{"claude-code", "code"}`). This unconditionally raised `NotImplementedError("Multi-channel dispatch not yet implemented")`, crashing `python -m factory.runner` with no config.

**Fix:** Filter out `channel="code"` before the set cardinality check:
```python
channels = set(rc.channel for rc in config.roles if rc.channel != "code")
```

**Tests:** Added `TestCreateChannel` in `tests/test_runner_coverage.py` with 4 cases:
1. Default config → `claude-code` (was failing before fix)
2. Phase 1 config → `claude-code`
3. Phase 2 opencode config → `opencode`
4. Multi-model config (`claude-code` + `opencode`) → raises `NotImplementedError`

**Result:** 259 passed, 1 skipped, 0 failed.

**Breadcrumb moved to resolved:** `breadcrumbs/resolved/041-create-channel-factory-counts-deterministic-channel.md`

---

## 2026-05-08 — Session 12: Implement BC-039 and BC-040

**Invocation:** Claude Code

**Focus:** Resolve two open breadcrumbs:
- BC-039: Lint gate auto-format + implementer prompt modern typing conventions
- BC-040: OpenCodeChannel adapter with per-role model selection

**Changes:**

1. `src/factory/gate.py` — `_run_ruff()` now runs `ruff check --fix` and `ruff format` before the final `ruff check`. Auto-fixes I001, UP006, UP035, UP045; only unfixable issues (e.g., bare `except`) produce gate_fail.

2. `src/factory/prompts/implementer.md` — Added **Typing conventions** section:
   - Use `X | Y` for unions, `X | None` for optionals; never `Union`, `Optional`
   - Use built-in generics `dict`, `list`, `set`, `tuple`; never `typing.Dict`, etc.
   - Import from `collections.abc` instead of `typing`
   - Import grouping rule

3. `src/factory/runner.py` — Added `_has_prior_gate_fail()` helper; `process_work_item()` now skips resumable-artifact logic when the work-item has prior `gate_fail` or `channel_fail` events. This prevents resubmitting a gate-rejected artifact.

4. `src/factory/output_extraction.py` — New shared module extracted from `claude_code_channel.py`. Contains model-agnostic `extract_artifact_from_output()` and `extract_json_from_output()`.

5. `src/factory/claude_code_channel.py` — Imports from `output_extraction.py`; re-exports private names for backward compatibility with existing tests.

6. `src/factory/opencode_channel.py` — New `OpenCodeChannel` implementing the `Channel` protocol:
   - Invokes `opencode run --dangerously-skip-permissions --model <provider/model>`
   - Per-role `model` selection via `RoleConfig.model`
   - Family derived from model provider prefix (`zai-coding-plan/*` → `zai`, `ollama-cloud/*` → `ollama`, etc.)
   - Same error handling pattern as `ClaudeCodeChannel`

7. `src/factory/runner.py` — Added `_create_channel()` factory replacing hardcoded `ClaudeCodeChannel` import in `main()`. Supports `opencode` and `claude-code` single-channel configs; raises `NotImplementedError` for multi-channel.

8. `tests/test_opencode_channel.py` — New test file: family derivation, artifact extension, channel properties.

9. `tests/test_pipeline_integration.py` — Updated `_BadImplIntegrationChannel` to produce a bare `except` (unfixable by ruff auto-format) so the escalation test still exercises repeated gate failures after the auto-format change.

**Test results:** 255 passed, 1 skipped, 0 failed.

**Breadcrumbs moved to resolved:**
- `breadcrumbs/resolved/039-lint-autofix-and-prompt-modern-typing.md`
- `breadcrumbs/resolved/040-opencode-channel-adapter.md`

---

## 2026-05-08 — Session 10: Wave 7 attempt — golden-run-002 FAILED, module resolution bug found and fixed, escalation no-op discovered

**Invocation:** OpenCode (glm-5.1)

**Focus:** Execute Wave 7 of Phase 2 implementation plan — golden-run-002 with real Claude CC across the full 3-stage pipeline (interface_spec → test_suite → implementation).

**Result: Golden run FAILED. 15/15 interface_specs locked, 15/15 test_suites locked, 0/15 implementations locked. 238/238 unit tests pass, lint clean.**

**Primary failure: Cross-work-item module resolution in subprocess gates.**

The implementation gate's `_run_pytest` and `_run_mypy` could not resolve imports from the `interface` module because the interface `.pyi`, test suite `.py`, and implementation `.py` artifacts lived in separate work-item directories. Test suites import `from interface import ...` (the canonical module name for the locked interface contract), but the implementation file was named `artifact.py` and wasn't on any Python import path. Every implementation attempt failed with `ImportError` on pytest collection.

**Fix applied:** Both `_run_pytest` and `_run_mypy` now create isolated temp directories with correct module names:
- Implementation copied as both its original filename and `interface.py` (for pytest)
- Interface `.pyi` copied alongside as `interface.pyi` (for mypy)
- Test suite copied alongside

**Secondary discovery: Escalation routing is a no-op (BC-037).**

When the router escalates an implementation item after exceeding `attempt_threshold`, it produces `cannot_proceed_seam` diagnostics targeting `interface_architect`. But the item goes back to state `new`, and the worker's `type_to_role` mapping always sends implementation items to the `implementer` role. The implementer re-claims and produces another failing artifact. Items cycled up to 80 times after escalation fired. BC-037 filed.

**Infrastructure changes:**

1. `ClaudeCodeChannel` — `_artifact_extension_for_role()` method: writes `.pyi` for `interface_architect`, `.py` for `test_author`/`implementer`.

2. `KimiAPIChannel` stub — `_artifact_extension_for_role()` added for symmetry.

3. `scheduler.py` — `interface_ref` now passed into `implementation` work items so the gate can resolve the `.pyi` stub.

4. `gate.py` — `_run_mypy` and `_run_pytest` create tempdirs with module aliases.

5. `router.py` — Fixed route map to send implementation failures to implementer, not test_author.

**Breadcrumbs closed:**
- BC-034: Cannot_proceed without diagnostics file causes double-release
- BC-035: InMemorySubstrate get_work_item rejects string UUIDs
- BC-036: InMemorySubstrate claim attempt_number resets after transition

---

## 2026-05-08 — Session 9: Wave 6 — golden-run-001 with 15 real Claude CC interface_spec items

**Invocation:** OpenCode (glm-5.1)

**Focus:** Run first golden run with real Claude CC headless against 15 curated specs, validate end-to-end pipeline with real substrate and real model.

**Result: 12/15 interface_specs locked, 3 escalated. 235/235 unit tests pass.**

**Failures:**
1. Concurrent claim test — interface spec declared a `concurrent_safe` flag but implementation gate's `_run_pytest` had no concurrency harness. Real bug; not a pipeline bug.
2. Adversarial item with deliberately broken syntax — correctly escalated to principal.
3. Ambiguous AC-07 / AC-08 overlap — interface spec vacuous; correctly escalated.

**Telemetry captured:** Per-event actor metadata with role/channel/family/attempt_n working end-to-end.

**New breadcrumbs filed:**
- BC-038: test_suite gate doesn't verify pytest collectability
- BC-039: Implementation lint gate should auto-format before checking
- BC-040: OpenCodeChannel adapter

---

## 2026-05-07 — Session 8: Wave 5 — cross-stage escalation routing

**Invocation:** Claude Code (Sonnet 4)

**Focus:** Build cross-stage escalation (BC-027) so repeated gate failures on a downstream role route back to the upstream contract.

**Changes:**

1. `src/factory/router.py` — `route()` function with `attempt_threshold`. After `attempt_n >= threshold`, gate failures transition to `cannot_proceed` (terminal) with `cannot_proceed_seam` diagnostics.

2. `src/factory/gate_process.py` — `process_gate_item()` now calls `route()` after evaluation.

3. `tests/test_router.py` — Phase 1 routing tests (gate_pass → locked, gate_fail → new).

4. `tests/test_router_phase2.py` — Phase 2 escalation tests:
   - impl_mypy / impl_pytest / impl_lint / impl_import → implementer below threshold
   - Same kinds → interface_architect at/above threshold
   - test_collect / test_import_forbidden → test_author below threshold
   - Same kinds → interface_architect at/above threshold
   - interface_spec failures never escalate (no upstream)

5. `workflows/phase2.yaml` — Added `gate_escalation` transition from `gating` to `cannot_proceed`.

**Test results:** 234 pass, 1 skip.

**Breadcrumbs closed:** BC-027

---

## 2026-05-07 — Session 7: Wave 4 — gate process + scheduler handoffs

**Invocation:** OpenCode (glm-5.1)

**Focus:** Mechanical gate process and scheduler idempotency.

**Changes:**

1. `src/factory/gate_process.py` — Full gate loop + `process_gate_item()` with per-type evaluation.

2. `src/factory/scheduler.py` — `_ensure_downstream_item()` with idempotency checks and per-source `custom_fields` ref validation.

3. `tests/test_scheduler_idempotency.py` — Duplicate handoff, second source, interface ref propagation.

4. `tests/test_gate_process.py` — Integration tests for gate pass / fail / missing artifact.

**Test results:** 224 pass, 1 skip.

**Breadcrumbs closed:**
- BC-025: evaluate_implementation missing subprocess gates
- BC-026: Scheduler idempotency

---

## 2026-05-07 — Session 6: Wave 3 — context derivation + prompt rendering

**Invocation:** Claude Code (Sonnet 4)

**Focus:** Build deterministic context derivation and prompt rendering for interface_architect, test_author, implementer.

**Changes:**

1. `src/factory/context.py` — `derive_context()`, `derive_test_author_context()`, `derive_implementer_context()`, `render_prompt()`.

2. `src/factory/prompts/` — Role-specific markdown templates:
   - `interface_architect.md` — produce locked `.pyi`
   - `test_author.md` — produce tests from AC + interface
   - `implementer.md` — produce implementation from interface + tests

3. `tests/test_context.py` — Determinism, hash differentiation, spec source priority, prompt inclusion.

4. `tests/test_failure_summary.py` — `derive_failures()` and `failures_to_json()` for structured prior-failure summaries.

**Test results:** 206 pass, 1 skip.

**Breadcrumbs closed:**
- BC-012: Context derivation tests should exercise both spec_file paths
- BC-014: Resume path untested at integration level

---

## 2026-05-06 — Session 5: Wave 2 — runner + workspace + channel adapter

**Invocation:** OpenCode (glm-5.1)

**Focus:** Build runner worker loop, workspace artifact management, and Claude Code channel adapter.

**Changes:**

1. `src/factory/runner.py` — `worker_loop()`, `process_work_item()`, failure handling, resume logic.

2. `src/factory/workspace.py` — `write_artifact()`, `find_resumable_artifact()`, `quarantine_attempt()`, SHA-256 manifest.

3. `src/factory/claude_code_channel.py` — `ClaudeCodeChannel` with `_extract_artifact_from_output()` and `_extract_json_from_output()`.

4. `tests/test_runner_smoke.py` — Full loop with mock channel.

5. `tests/test_runner_idempotency.py` — Resume after crash, manifest tampering, multi-crash.

6. `tests/test_runner_resume.py` — `_resume_and_submit()` integration tests.

7. `tests/test_workspace.py` — Round-trip, overwrite safety, resumable search, quarantine.

8. `tests/test_channel_failures.py` — Timeout, non-zero exit, empty output, extraction failure.

**Test results:** 175 pass, 1 skip.

**Breadcrumbs closed:**
- BC-006: MockSubstrate needed for CI-portable tests
- BC-007: Integration tests are stubs
- BC-011: Test gap — claim transition not asserted
- BC-019: Channel failure modes untested
- BC-020: Config YAML loading untested
- BC-021: Non-cannot_proceed channel failures produce no substrate event
- BC-024: _resume_and_submit hardcodes role

---

## 2026-05-06 — Session 4: Wave 1 — config + gate skeleton

**Invocation:** Claude Code (Sonnet 4)

**Focus:** Build config loader and mechanical gate skeleton.

**Changes:**

1. `src/factory/config.py` — `FactoryConfig` dataclass with `from_yaml()`, `from_yaml_or_default()`, `get_role_config()`.

2. `src/factory/gate.py` — `evaluate_interface_spec()`, `evaluate_test_suite()`, `evaluate_implementation()` with syntax, stub, structural-semantic, import, mypy, pytest, ruff gates.

3. `tests/test_config.py` — YAML round-trip, malformed handling, role lookup.

4. `tests/test_gate_interface_spec.py` — Happy path, syntax error, stub check, AC reference, structural semantics.

5. `tests/test_gate_test_suite.py` — File exists, empty, syntax, forbidden import, collect-only.

6. `tests/test_gate_implementation.py` — Happy path, file not found, empty, syntax.

7. `tests/test_gate_implementation_subprocess.py` — Import gate, ruff gate, pytest gate, gate order.

8. `workflows/phase1.yaml` — Single-role workflow (interface_spec → gating → locked).

9. `workflows/phase2.yaml` — Three-role workflow with handoff transitions.

**Test results:** 128 pass, 1 skip.

**Breadcrumbs closed:**
- BC-002: Runner skeleton complexity risk
- BC-003: Runner idempotency on restart
- BC-004: cannot_proceed routing has no workflow path
- BC-005: Spec content resolution
- BC-008: Fixture AC-15 mislabel
- BC-009: context_hash → artifact non-determinism
- BC-010: populate_work_items.py --reset does not clean workspace
- BC-013: Gate is syntactic-only
- BC-015: Integration test private substrate API coupling
- BC-016: AC reference check uses substring search
- BC-017: Router is dead code
- BC-018: MockSubstrate diverges from real substrate
- BC-022: Integration tests access substrate private API
- BC-023: Structural semantics gate rejected module-level AC docstrings

---

## 2026-05-06 — Session 3: Repository setup + spec read

**Invocation:** OpenCode (glm-5.1)

**Focus:** Read spec, scan existing codebase, understand current state.

**Observations:**

- Phase 0 design repo; no runner code yet.
- spec.md is authoritative.
- substrate dependency is real; Phase 1 blocked on BC-021.
- breadcrumbs directory exists with 12 open items (BC-001 through BC-012).

**No code changes.**

---

## 2026-05-05 — Session 2: Design review

**Invocation:** Claude Code (Sonnet 4)

**Focus:** Review spec.md with principal; validate phasing decisions.

**Key decisions:**
- Phase 1 will use Claude CC headless only.
- Phase 3 adds fleet; Phase 4 adds jury/race.
- Do not skip phasing; the v1 lesson is real.

**No code changes.**

---

## 2026-05-05 — Session 1: Kickoff

**Invocation:** OpenCode (glm-5.1)

**Focus:** Initialize repo, write spec.md, write AGENTS.md.

**Files created:**
- `spec.md` — authoritative design spec
- `AGENTS.md` — agent conventions and pointers
- `breadcrumbs/README.md` — breadcrumb schema and index
- `.factory/worklog.md` — this file

**No tests yet.**

---
