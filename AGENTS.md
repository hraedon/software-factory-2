# Software Factory v2 — Agent Guide

## Orientation

Read in this order:
1. `spec.md` — design spec, authoritative for every architectural decision.
2. `breadcrumbs/README.md` — open defects/design questions/RFCs, sorted by severity.
3. `.factory/worklog.md` — most recent session entry, for current state.
4. `.factory/reflections/` — most recent reflection, for the prior agent's subjective read.

## What this project is

A pipeline that consumes a Level-1+ spec (produced by socratic-specification) and produces working, tested software for line-of-business tooling. Substrate (`/projects/substrate`) is the coordination/state spine.

The principal of this project is a **systems architect, not a developer**. Architectural decisions must respect that constraint: do not propose interventions that require code review, and do not assume the principal can debug subtle implementation bugs. Their value lands in spec quality, AC clarity, and outcome-level evaluation.

## Conventions

### Spec authority
- `spec.md` is authoritative. Implementation drift requires a spec amendment with rationale, not silent divergence.
- Spec amendments are made with a breadcrumb resolution note. Precedent: substrate BC-008.

### Breadcrumbs
- One file per defect/design-question/improvement under `breadcrumbs/`.
- Active bugs and improvements use numeric prefixes (`054`, `055`).
- Design proposals awaiting future phases use `RFC-` prefixes (`RFC-001`, `RFC-002`). RFCs are NOT actionable yet — they are recorded design decisions for later stages.
- Resolved items move to `breadcrumbs/resolved/` and the README index is updated.
- Same schema as substrate's `breadcrumbs/`. Reuse that README's frontmatter format.
- Use the `dep-substrate-*` tag for breadcrumbs that block on substrate work.
- Use the `dep-v1-NNN` tag for breadcrumbs that block on lessons from v1 factory.

### Default values
- All defaults live in `FactoryConfig` or are derived from it. No inline defaults, no hardcoded identifiers, no bare strings in function bodies that could appear in another file. Precedent: v1's "string constant gravity" where `"claude"` accreted into 7 copies across 5 files.

### Worklog and reflections
- `.factory/worklog.md` — reverse-chronological session log. Prepend new entries.
- `.factory/reflections/` — per-session subjective notes. One file per session, written via the `/reflect` skill.

### Session lifecycle
- `/reflect` — write a session reflection (system skill).
- `/end` — wrap up: update breadcrumbs, run reflect, commit (system skill).

## Status

**Phase 5 (integration and outcome verification).** Phase 4 exit criteria met at GR-027 (88% lock rate, dual-family jury K2+DeepSeek, all constraint paths exercised). Phase 5 implements Stage 8 (integration) and Stage 9 (outcome verification) per spec §4, and addresses review/jury verdict routing (BC-145) alongside pipeline-flow changes.

**What exists:**
- 7-module runner: runner, gate, gate_process, router, scheduler, config, workspace
- 3 channel adapters: ClaudeCodeChannel, OpenCodeChannel (K2/GLM/DeepSeek via model selection); GeminiCLIChannel disabled (unvalidated)
- Multi-channel dispatch: runner selects channel per-role based on config binding
- Multi-model jury: parallel invocation of distinct models through same adapter via `model_override`; unique juror keys by channel+model
- Credential infrastructure: `~/.config/factory/credentials.yaml` for provider API keys
- 5 workflow YAMLs: phase1.yaml, phase2.yaml, phase3.yaml, phase4.yaml (review + jury), full_pipeline.yaml
- Spec lint integrated into `populate_work_items.py` (BC-127)
- 688 passing tests, 0 lint errors
- Inner gate telemetry: submit payloads carry `inner_gate_attempts`; telemetry reports inner gate first-pass rate (BC-133)
- Jury observability: `disagreement_rationale` always populated when quorum not met; `[all_against]` tag for all-failure cases (BC-134)
- 27 golden runs executed (GR-001 through GR-027)
  - GR-027: Phase 4 exit artifact — cert-watch full DAG, dual-family jury (K2 + DeepSeek), 30/34 locked (88%), jury_disagree exercised, 0 stuck, 4 properly escalated
  - GR-025: Mixed-family jury (K2 + glm-5.1 via z.ai), jury_quorum=2; jury_disagree exercised
  - GR-022: Phase 4 first run — 100% lock rate (15/15) on cert-watch-mini, all 5 roles exercised
  - GR-021: 100% lock rate (24/24) on cert-watch full DAG, K2-only; inner gate first-attempt rate 74%

**Known issues:** 2 open breadcrumbs (0 critical, 1 high, 1 medium, 0 low) + 18 RFCs. See `breadcrumbs/README.md`.
- BC-145 (high, in_progress): review/jury verdict routing — shape alongside Phase 5 pipeline-flow changes
- BC-138 (medium, proposed): Qwen 3.6-27b operational timeout on test_author and implementer roles

**Blocking on:** nothing. All validated channels have working adapters; unvalidated adapters disabled.

**Phase 4 exit criteria** (defined in `spec.md` §10, assessed at GR-027):
- Lock-within-budget rate ≥ 90% — **88% (near-miss; accepted with cause analysis)**
- Mean attempts to lock ≤ 2.0 — **met: 1.88**
- Inner-gate first-pass rate ≥ 60% — **met: 71%**
- Review first-attempt pass rate ≥ 80% — **met: 83%**
- Jury quorum-met rate ≥ 90% — **80% (near-miss; one disagreement case)**
- Unknown gate-name rate for review/jury events = 0% — **met: 0%**
- Multi-family jury exercised — **met (K2 + DeepSeek)**
- Jury disagreement path exercised — **met**
- Review rejection path exercised — **met**
- Channel failover exercised — **met**
- Gate budget ≤ 15 — **met: 15**

**Phase 5 work:**
1. Implement `integrator` role and `integration` work item type (Stage 8).
2. Implement `outcome_verifier` role and outcome-verification work items (Stage 9).
3. Design review/jury verdict upstream routing (BC-145) — structured feedback to implementer/interface_architect instead of terminal retry.
4. Build integration mechanical gates: cross-module import, assembled-tree mypy, cross-cutting pytest.
5. Validate on synthetic multi-module fixtures before first real workload.

## What not to build yet

The phasing in `spec.md` §10 exists to prevent the v1 mistake of building the whole architecture at once. Current constraints:
- Five-role pipeline (interface_architect, test_author, implementer, cross_family_reviewer, frontier_judge). Roles beyond these (integrator, outcome_verifier, coherence_reviewer) have no implementation.
- Mechanical gates + single-channel review/jury gates. Multi-family jury racing is validated in skeleton but awaiting first golden-run exercise.
- Multi-model jury: parallel invocation of distinct models through same adapter via `model_override`; unique juror keys by channel+model suffix. Validated in GR-025 (K2 + glm-5.1).
- No integration or outcome-verification stages until Phase 5.
- Channel adapters for DeepSeek (standalone Ollama adapter) and Gemini exist but are not yet validated in golden runs. The Gemini CLI errors with `SyntaxError: Invalid regular expression flags` under the system Node (`/usr/bin/node` is v18); a newer Node is available via nvm at `~/.nvm/versions/node/v24.15.0/bin/node` — source `~/.nvm/nvm.sh && nvm use 24` (or invoke that node binary directly) before running `gemini`.
If you find yourself wanting to skip ahead, file a breadcrumb explaining why and let the principal decide.

## Pointers

- Substrate repo: `/projects/substrate`
- Socratic-specification repo (Stage 0 source): `/projects/socratic-specification`
- v1 software factory (reference for *what not to do*, not for code reuse): `/projects/software-factory`

## Testing

```bash
make test        # 550 tests, ~76s
make lint        # ruff check + format (no errors)
make audit       # vulture dead-code check (no findings)
make integration # @pytest.mark.integration only (requires Postgres)
make check       # lint + audit + test (full CI gate)
```

## Golden runs

The pipeline runs 3–4 concurrent processes (runner, gate, scheduler) against a PostgreSQL database and a real model channel. Phase 4 adds review + jury work items; runner and gate handle them transparently.

### Prerequisites

- PostgreSQL running: `docker compose -f /projects/substrate/docker-compose.test.yml up -d`
- Model channel available. For `opencode` channel: `opencode` CLI must be in PATH (installed at `~/.opencode/bin/opencode`). Auth is handled internally by opencode — no `FIREWORKS_API_KEY` env var needed. Verify with `opencode run --dangerously-skip-permissions --model <model> --help`.

### Execution

```bash
# 1. Create config YAML (copy a prior golden-run-NNN-config.yaml, change project_name and workspace_root)
# 2. Populate work items from fixture (--workflow inferred from config)
make golden-run CONFIG=golden-run-022-config.yaml FIXTURES=tests/fixtures/cert-watch-mini
# 3. This runs populate, then runner+gate+scheduler in parallel, then telemetry
```

For manual step-by-step control (recommended for monitoring):

```bash
.venv/bin/python populate_work_items.py --config golden-run-022-config.yaml --reset --fixtures tests/fixtures/cert-watch-mini
.venv/bin/python -m factory.runner --config golden-run-022-config.yaml > /tmp/gr022-runner.log 2>&1 &
.venv/bin/python -m factory.gate_process --config golden-run-022-config.yaml > /tmp/gr022-gate.log 2>&1 &
.venv/bin/python -m factory.scheduler --config golden-run-022-config.yaml > /tmp/gr022-scheduler.log 2>&1 &
wait
.venv/bin/python -m factory.telemetry --config golden-run-022-config.yaml
.venv/bin/python -m factory.telemetry --verify --config golden-run-022-config.yaml
```

### Monitoring

Check progress while running:
```bash
tail -20 /tmp/gr022-runner.log
tail -10 /tmp/gr022-scheduler.log
tail -10 /tmp/gr022-gate.log
```

### Monitoring

Check progress while running:
```bash
tail -20 /tmp/gr019-runner.log
tail -10 /tmp/gr019-scheduler.log
tail -10 /tmp/gr019-gate.log
```

Processes are idle when no new log lines appear for >60s. Kill with `kill <PID>` or `kill -9 <PID>` if needed, then run telemetry.

### Agent-mediated golden runs (BC-140 protocol)

When an agent (e.g. OpenCode, GLM, Claude Code) executes a golden run on behalf of the principal, use the supervised wrapper to prevent context pollution, unbounded budget burn, and data loss:

```bash
python scripts/agent_golden_run.py \
  --config golden-run-NNN-config.yaml \
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
   - Launches runner/gate/scheduler from `/tmp`, never from the repo root.
   - Prevents opencode session DB pollution (the GR-026 failure mode).

3. **Process supervision**:
   - Runs `populate_work_items.py` with `--reset`.
   - Launches all three processes in background, captures PIDs.
   - Tails logs every 30s automatically.

4. **Monitoring guardrails** (pause and alert if tripped):
   - `claim_near_budget` — item at attempt threshold; hard-stop already enforced in runner (BC-139), but ≥3 such items indicates systemic failure.
   - `gate_failed.*cross_family_review` — review item cycling; kills run if ≥3 occurrences.
   - `gate_failed.*jury` — jury item cycling; kills run if ≥3 occurrences.
   - `channel_invoke_failed` — model channel down/rate-limited; kills run if ≥5 occurrences.
   - Idle detection: no new log lines for 90s → assumes completion, runs telemetry.

5. **Cleanup** (never touches application state):
   - Removes workspace directory (`/tmp/sf2-golden-NNN`).
   - Removes log files (`/tmp/grNNN-*.log`).
   - **Never** touches `~/.local/share/opencode/opencode.db` or any other application state store.

The wrapper runs non-interactively (auto-cleans), making it suitable for unattended agent execution. The principal can check in periodically; if a guardrail trips, the script exits with a loud fatal message and the processes remain in background for inspection.

### Post-run documentation

Every golden run must leave an audit trail. After telemetry completes:

1. **Preserve the workspace** (if the run is significant, failed in a novel way, or is the first of a new phase):
   ```bash
   cp -r /tmp/sf2-golden-NNN .factory/grNNN-workspace-backup
   ```
   Keep it outside git (add to `.gitignore` or just don't `git add` it). Workspaces are large and should not bloat the repo.

2. **Write a golden-run log** at `.factory/golden-run-NNN-log.md` following the existing format:
   - Result summary table (locked, stuck, cannot_proceed counts)
   - Per-stage detail (interface_spec, test_suite, implementation, review, jury)
   - Failure analysis with root cause
   - Telemetry output
   - Phase exit criteria assessment
   - Comparison with prior runs
   - Artifacts preserved list
   - Lessons / next steps

   See `.factory/golden-run-026-log.md` for a reference that includes failure-mode documentation (BC-139) and agent execution mistakes (BC-140).

3. **Commit the log and config:**
   ```bash
   git add .factory/golden-run-NNN-log.md golden-run-NNN-config.yaml
   git commit -m "GR-NNN log: <one-line summary>"
   ```

**Rule for agents:** If asked to execute a golden run, always use `scripts/agent_golden_run.py`. Never run `make golden-run` or the raw `python -m factory.runner` commands directly.
