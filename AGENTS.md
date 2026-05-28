# Software Factory v2 — Agent Guide

> **Upstream renamed 2026-05-27:** the coordination spine was previously `substrate`; it is now `regista` (consumer migration in `plans/2026-05-27-substrate-rename-consumer-migration.md`, regista Plan 018 upstream). The test DSN database `substrate_test` was renamed to `regista_test`. Older `.factory/` history, breadcrumbs, reflections, and debate documents that still say "substrate" are intentional historical record; `dep-graph-viewer` fixture's "large substrates" wording is the generic noun, not the project name.

## Orientation

Read in this order:
1. `spec.md` — design spec, authoritative for every architectural decision.
2. `breadcrumbs/README.md` — open defects/design questions/RFCs, sorted by severity.
3. `.factory/worklog.md` — most recent session entry, for current state.
4. `.factory/reflections/` — most recent reflection, for the prior agent's subjective read.

## What this project is

A pipeline that consumes a Level-1+ spec (produced by socratic-specification) and produces working, tested software for line-of-business tooling. Regista (`/projects/regista`) is the coordination/state spine.

The principal of this project is a **systems architect, not a developer**. Architectural decisions must respect that constraint: do not propose interventions that require code review, and do not assume the principal can debug subtle implementation bugs. Their value lands in spec quality, AC clarity, and outcome-level evaluation.

## Conventions

### Spec authority
- `spec.md` is authoritative. Implementation drift requires a spec amendment with rationale, not silent divergence.
- Spec amendments are made with a breadcrumb resolution note. Precedent: regista BC-008.

### Breadcrumbs
- One file per defect/design-question/improvement under `breadcrumbs/`.
- Active bugs and improvements use numeric prefixes (`054`, `055`).
- Design proposals awaiting future phases use `RFC-` prefixes (`RFC-001`, `RFC-002`). RFCs are NOT actionable yet — they are recorded design decisions for later stages.
- Resolved items move to `breadcrumbs/resolved/` and the README index is updated.
- Same schema as regista's `breadcrumbs/`. Reuse that README's frontmatter format.
- Use the `dep-regista-*` tag for breadcrumbs that block on regista work.
- Use the `dep-v1-NNN` tag for breadcrumbs that block on lessons from v1 factory.
- Defect classes (`CLASS-NNN-*.md`) group individual BCs with the same shape. Before filing a new BC, scan `CLASS-*.md` instances tables. If 3rd instance of an unclassified shape, file a CLASS file.

### Default values
- All defaults live in `FactoryConfig` or are derived from it. No inline defaults, no hardcoded identifiers, no bare strings in function bodies that could appear in another file. Precedent: v1's "string constant gravity" where `"claude"` accreted into 7 copies across 5 files.

### Worklog and reflections
- `.factory/worklog.md` — reverse-chronological session log. Prepend new entries.
- `.factory/reflections/` — per-session subjective notes. One file per session, written via the `/reflect` skill.

### Session lifecycle
- `/reflect` — write a session reflection (system skill).
- `/end` — wrap up: update breadcrumbs, run reflect, commit (system skill).

## Status

- **Phase 5 complete.** Phase 5 exit validated at GR-038 (first all-pass full-DAG run). 39 golden runs executed through GR-039 (RFC-011 + BC-195 validation under K2). All 211 BCs resolved; zero open bugs.
- **Phase 6 in progress.** RFC-023 Phase A (deterministic decomposer) validated through GR-039. Phase B (model-driven semantic naming + FR grouping) implemented in Session 50: prompt template, structured prompt builder, semantic naming gates (fr-shaped, generic suffixes, length, snake_case), prior-failure feedback, Phase A fallback. Snapshot tests for three workloads (cert-watch, log-redact-cli, dep-graph-viewer) passing.
- **W3/W4/W5 remaining:** GR-040 baseline golden run on new workloads via Phase A; GR-041 Phase B golden run with real model channel; decision gate writeup updating Phase 6 status.

**What exists:**
- 7-module runner: runner, gate, gate_process, router, scheduler, config, workspace
- 3 channel adapters: ClaudeCodeChannel (validated), OpenCodeChannel (validated, K2/GLM/DeepSeek), GeminiCLIChannel (validated, disabled in defaults)
- Multi-model jury: parallel invocation of distinct models via `model_override`
- 6 workflow YAMLs with `extends:` composition (phase1–5, full_pipeline)
- Unified subprocess wrapper (RFC-011): all subprocess calls use `factory.subprocess.run`
- Spec lint, inner gate telemetry, jury observability, credential infrastructure
- **1107 passing tests, 0 lint errors, 0 dead code findings** (run `make check` to verify current counts)

**Known issues:** 5 open bugs (1 high, 3 medium, 1 low) + 17 RFCs + 7 active defect classes + 2 stabilized (228 resolved). See `breadcrumbs/README.md`.

**Blocking on:** nothing.

### Phase 6 gate items (priority order)

1. **RFC-023 (decomposer)** — Phase A (deterministic) implemented: reads `spec.yaml` or `spec.md`, produces per-FR fixture `.md` files. **Phase B (model-driven):** implemented in Session 50 — new `decomposer.md` prompt with semantic naming rules, structured prompt builder (`_build_structured_prompt`), semantic naming gate (`fr\d+`, generic suffix, length, snake_case), prior-failure feedback, Phase A fallback. Snapshot tests for three workloads passing. Awaiting W3/W4 golden-run validation.
2. **RFC-026 (principal review surface)** — implemented: `src/factory/review_surface.py` generates `REVIEW.md` + `review.json` from regista state. Human-readable module summaries, cannot-proceed detail, artifact listings.
3. **RFC-022 (initiative primitive)** — implemented: `src/factory/initiative.py` provides `generate_initiative_id()`, `query_initiatives()`, `cancel_initiative()`, `requeue_initiative()`. `populate_work_items.py` assigns initiative IDs at populate time. Regista-dependent operations require `initiative_id` custom field in workflow YAML (integration tests).
4. **RFC-024 (coherence reviewer)** — removed per Option A; role deleted from all configuration. May be reintroduced in Phase 6 with concrete evidence of a structural-coherence gap.
5. **RFC-027 (test efficacy)** — no mechanical verification that tests validate behavior.

**Phase 4 exit criteria** (defined in `spec.md` §10, assessed at GR-027): all met or near-miss with cause analysis. Lock-within-budget 88%, mean attempts 1.88, inner-gate first-pass 71%, review first-attempt 83%, jury quorum-met 80%, unknown gate-name rate 0%, multi-family jury exercised, disagreement/rejection paths exercised, channel failover exercised, gate budget 15.

## What not to build yet

The phasing in `spec.md` §10 exists to prevent the v1 mistake of building the whole architecture at once. Current constraints:
- Seven worker roles implemented: interface_architect, test_author, implementer, cross_family_reviewer, frontier_judge, integrator, outcome_verifier. The `coherence_reviewer` role was removed from dead configuration (RFC-024 Option A, 2026-05-22); it may be reintroduced in Phase 6 if real workloads demonstrate a structural-coherence gap that integrator + outcome_verifier miss.
- Multi-family jury (parallel model invocation via `model_override`) validated in GR-025+.
- Integration and outcome-verification stages implemented and validated (GR-031 through GR-038).
- Channel adapters: ClaudeCodeChannel (validated), OpenCodeChannel (validated, handles Kimi/DeepSeek/GLM via model selector), GeminiCLIChannel (validated in GR-032+, disabled in defaults pending better pass-rate data). The Gemini CLI requires Node 24: `PATH="$HOME/.nvm/versions/node/v24.15.0/bin:$PATH"` before running `gemini`.
If you find yourself wanting to skip ahead, file a breadcrumb explaining why and let the principal decide.

## Pointers

- Regista repo: `/projects/regista`
- Socratic-specification repo (Stage 0 source): `/projects/socratic-specification`
- v1 software factory (reference for *what not to do*, not for code reuse): `/projects/software-factory`

## Testing

```bash
make test        # 1107 tests, ~130s
make lint        # ruff check + format (no errors)
make audit       # vulture dead-code check (no findings)
make integration # @pytest.mark.integration only (requires Postgres)
make check       # lint + audit + test (full CI gate)
```

## Golden runs

The pipeline runs 3–4 concurrent processes (runner, gate, scheduler) against a PostgreSQL database and a real model channel. Phase 4 adds review + jury work items; runner and gate handle them transparently.

### Prerequisites

- PostgreSQL running: `docker compose -f /projects/regista/docker-compose.test.yml up -d`
- Model channel available. For `opencode` channel: `opencode` CLI must be in PATH (installed at `~/.opencode/bin/opencode`). Auth is handled internally by opencode — no `FIREWORKS_API_KEY` env var needed. Verify with `opencode run --dangerously-skip-permissions --model <model> --help`.

### Execution

```bash
# 1. Create config YAML (copy a prior config from .factory/golden-runs/, change project_name and workspace_root)
# 2. Populate work items from fixture (--workflow inferred from config)
make golden-run CONFIG=.factory/golden-runs/golden-run-022-config.yaml FIXTURES=tests/fixtures/cert-watch-mini
# 3. This runs populate, then runner+gate+scheduler in parallel, then telemetry
```

For manual step-by-step control (recommended for monitoring):

```bash
.venv/bin/python populate_work_items.py --config .factory/golden-runs/golden-run-022-config.yaml --reset --fixtures tests/fixtures/cert-watch-mini
.venv/bin/python -m factory.runner --config .factory/golden-runs/golden-run-022-config.yaml > /tmp/gr022-runner.log 2>&1 &
.venv/bin/python -m factory.gate_process --config .factory/golden-runs/golden-run-022-config.yaml > /tmp/gr022-gate.log 2>&1 &
.venv/bin/python -m factory.scheduler --config .factory/golden-runs/golden-run-022-config.yaml > /tmp/gr022-scheduler.log 2>&1 &
wait
.venv/bin/python -m factory.telemetry --config .factory/golden-runs/golden-run-022-config.yaml
.venv/bin/python -m factory.telemetry --verify --config .factory/golden-runs/golden-run-022-config.yaml
```

### Monitoring

Check progress while running:
```bash
tail -20 /tmp/gr022-runner.log
tail -10 /tmp/gr022-scheduler.log
tail -10 /tmp/gr022-gate.log
```

Processes are idle when no new log lines appear for >60s. Kill with `kill <PID>` or `kill -9 <PID>` if needed, then run telemetry.

### Agent-mediated golden runs (BC-140 protocol)

When an agent (e.g. OpenCode, GLM, Claude Code) executes a golden run on behalf of the principal, use the supervised wrapper to prevent context pollution, unbounded budget burn, and data loss:

```bash
python scripts/agent_golden_run.py \
  --config .factory/golden-runs/golden-run-NNN-config.yaml \
  --fixtures tests/fixtures/cert-watch-mini \
  --log-prefix grNNN
```

The wrapper enforces the BC-140 safety protocol:

1. **Pre-flight checks** (abort if any fail):
   - Scans `breadcrumbs/README.md` for open **critical** items — refuses to run if any exist.
   - Warns on open **high** items.
   - Validates `attempt_threshold <= 3` in config YAML.
   - Validates `workspace_root` is outside the repo directory.
   - Validates fixtures path exists.

2. **Workspace isolation**:
   - Launches runner/gate/scheduler from repo root (opencode requires project context).
   - Sets `XDG_DATA_HOME` to a temp directory per run so opencode session state is isolated from the principal's persistent store. No factory sessions clutter the principal's UI. If `--no-cleanup` is passed, that isolated DB dir is preserved and can be captured alongside the workspace for post-run forensics.

3. **Process supervision**:
   - Runs `populate_work_items.py` with `--reset`.
   - Launches all three processes in background, captures PIDs.
   - Tails logs every 30s automatically.

4. **Monitoring guardrails** (pause and alert if tripped):
   - `claim_near_budget` — WARN-ONLY; hard-stop enforced in runner (BC-139) and gate (BC-186), so this is expected terminal behavior, not a runaway signal. Retired as fatal post-BC-139/BC-186.
   - `gate_failed.*cross_family_review` — WARN-ONLY; post-BC-180/BC-185, gate_fail is the legitimate REVIEW_FOUND_DEFECT path creating upstream revisions. 3+ across different items is normal pipeline activity. Retired as fatal.
   - `gate_failed.*jury` — WARN-ONLY; same rationale as cross_family_review. BC-181 (gate_near_budget) and BC-182 (self-circuit-breaker) cover crash-loop detection. Retired as fatal.
   - `channel_invoke_failed` — model channel down/rate-limited; kills run if ≥5 occurrences. The only remaining fatal threshold.
   - Idle detection: no new log lines for 15 min (30 cycles × 30s) → assumes completion, runs telemetry.

   **RFC-033 — guardrail tagging requirement**: whenever you add or modify a guardrail (any code path that aborts or escalates based on a heuristic threshold), you must add two inline comment lines immediately above the threshold: `# Precondition: <BC or invariant that makes the failure mode possible>` and `# Audit trigger: re-evaluate when <specific condition>`. See `breadcrumbs/RFC-033-guardrail-lifecycle.md` for rationale and worked examples. Three guardrails falsely killed healthy runs this week because their preconditions changed without triggering re-evaluation.

5. **Cleanup** (never touches application state):
   - Removes workspace directory (`/tmp/sf2-golden-NNN`).
   - Removes log files (`/tmp/grNNN-*.log`).
   - Removes isolated opencode DB directory (`/tmp/sf2-golden-grNNN-opencode-data/opencode/`).
   - **Never** touches the principal's persistent store at `~/.local/share/opencode/`.

The wrapper runs non-interactively (auto-cleans), making it suitable for unattended agent execution. The principal can check in periodically; if a guardrail trips, the script exits with a loud fatal message and the processes remain in background for inspection.

### How to create and run a new Golden Run (step-by-step)

**Rule for agents:** If asked to execute a golden run, always use `scripts/agent_golden_run.py`. Never run `make golden-run` or the raw `python -m factory.runner` commands directly. Running the raw commands causes context pollution, unbounded budget burn, and data loss (see BC-140 / GR-026).

#### Step 0: Determine the run number

Look in `.factory/golden-runs/` for the highest existing number. The next run is `golden-run-NNN-config.yaml` and `golden-run-NNN-log.md` where `NNN` is the next integer.

#### Step 1: Verify available models and channels

**Before creating a config, verify the models you want to use are actually available.** Other agents often fail because they specify models or channels that don't exist.

Check available channels:
- `opencode` — run `opencode run --dangerously-skip-permissions --model <model> --help` for each model you plan to use.
- `claude-code` — run `claude --print --dangerously-skip-permissions --model <model> --help` for each model.
- `gemini-cli` — requires Node 24: `PATH="$HOME/.nvm/versions/node/v24.15.0/bin:$PATH" gemini -p - --yolo --skip-trust -m <model> --help`

**Valid channel names in configs:** `opencode`, `claude-code`, `gemini-cli`, `code` (for mechanical_gate only). **Do NOT use** `claude`, `gemini`, `fireworks`, `kimi` as channel names — they will fail with "Unknown channel".

**Valid model names depend on the channel:**
- For `opencode`: check `~/.config/opencode/opencode.json` under `provider.*.models` keys. Examples: `fireworks-ai/accounts/fireworks/routers/kimi-k2p6-turbo`, `mac-studio-lms/qwen/qwen3.6-27b`.
- For `claude-code`: use alias names like `sonnet`, `opus`, or full names like `claude-sonnet-4-6`.
- For `gemini-cli`: use `gemini-2.5-pro`, `gemini-2.5-flash`.

#### Step 2: Copy and modify a prior config

Pick a reference config from `.factory/golden-runs/` that matches the phase and model combination you want. Copy it:

```bash
cp .factory/golden-runs/golden-run-031-config.yaml .factory/golden-runs/golden-run-NNN-config.yaml
```

**Edit these fields (and ONLY these):**
- `project_name`: change to `sf2_golden_NNN` (must be unique per run)
- `workspace_root`: change to `/tmp/sf2-golden-NNN` (must be outside repo)
- `roles`: adjust channel/model bindings for the experiment you want to run
- `jury_quorum`: adjust if changing jury size (default 2)
- `fixture`: change `--fixtures` argument when running

**Keep everything else identical** to the reference config: `workflow_version`, `stage_topology`, `dsn`, `hmac_key_path`, `attempt_threshold` (must be ≤3), `inner_gate_retries` (must be ≤2).

**Common config mistakes:**
- Using `channel: claude` instead of `channel: claude-code` → "Unknown channel" crash
- Using `channel: gemini` instead of `channel: gemini-cli` → same crash
- `workspace_root` inside repo directory → pre-flight abort
- `attempt_threshold > 3` → pre-flight abort
- `project_name` colliding with a prior run → regista confusion

#### Step 3: Run the golden run using the wrapper

```bash
.venv/bin/python scripts/agent_golden_run.py \
  --config .factory/golden-runs/golden-run-NNN-config.yaml \
  --fixtures tests/fixtures/cert-watch-mini \
  --log-prefix grNNN
```

**Use `--no-cleanup` if you want to preserve the workspace for post-run forensics.**

The wrapper handles everything: pre-flight checks, population, process launch, monitoring, telemetry, and cleanup. Do NOT try to run the steps manually.

**During the run:**
- The wrapper prints status every 30s. Watch for danger signals.
- If it exits with `[FATAL]`, read the message carefully — it usually tells you exactly what went wrong (critical breadcrumbs, model ping failure, config validation error, etc.).
- Do NOT interrupt the processes manually. The wrapper waits for idle detection (no log lines for 10 minutes) before declaring done.

#### Step 4: Post-run forensics (do this BEFORE writing the log)

If the run failed or had unexpected results, **investigate before writing the log**:

1. **Read the telemetry output** — it's printed at the end by the wrapper.
2. **Check logs:** `.factory/logs/grNNN/runner.log`, `gate.log`, `scheduler.log`
3. **Search for failures:**
   ```bash
   grep -n "gate_failed\|cannot_proceed\|claim_near_budget\|channel_invoke_failed" .factory/logs/grNNN/runner.log
   grep -n "gate_failed\|gate_pass" .factory/logs/grNNN/gate.log
   ```
4. **If integration stage failed, check for BC-174-class issues:**
   - Reproduce the gate logic with both `.venv/bin/python` and the workspace's `.venv-gate/bin/python`
   - If the gate venv succeeds but factory venv fails, you found an environmental mismatch (file a BC)
5. **Preserve the workspace** if the failure is novel:
   ```bash
   cp -r /tmp/sf2-golden-NNN .factory/grNNN-workspace-backup
   ```

#### Step 5: Write the golden-run log

Create `.factory/golden-runs/golden-run-NNN-log.md`. Follow the exact format of prior logs. **Required sections:**

- **Header**: Date, config name, channels used, fixture, executor, wall clock
- **Purpose**: Why this run was executed (what hypothesis are you testing?)
- **Result summary table**: Total items, locked count + %, cannot_proceed, stuck, mean attempts, first gate-evaluation pass rate, inner gate first-pass rate, unknown gate rate, deterministic gate rate, verify passed
- **Per-stage detail**: One subsection per stage with items locked / failed and specific gate names
- **Failure analysis**: For each failure, state the **actual root cause**, not a guess. If you don't know, say "root cause unknown — requires forensics."
- **Model-family performance comparison**: If comparing against prior runs, include a table
- **BC-145 upstream routing**: Whether REVIEW_FOUND_DEFECT was exercised
- **Claim-near-budget behavior**: Whether hard-stops worked correctly
- **Channel health**: Per-channel outcomes and stability notes
- **Telemetry integrity**: unknown_gate_name_count, orphan_submit_count, unmatched_gate_count, verify_passed
- **Artifacts preserved**: Where workspace/logs are kept
- **Lessons and next steps**: Numbered list of concrete takeaways

**Critical:** If you discover the root cause of a failure was different from your initial assessment (as happened with GR-032 and BC-174), **update the log with the corrected analysis**. Don't leave wrong root causes in the audit trail.

#### Step 6: Commit

```bash
git add .factory/golden-runs/golden-run-NNN-config.yaml .factory/golden-runs/golden-run-NNN-log.md
git commit -m "GR-NNN: <one-line summary>"
```

If you fixed bugs discovered during the run, commit those separately with a clear message referencing the BC number.
