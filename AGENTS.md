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

**Phase 3 (current).** Fleet integration. Phase 2 (sequential single-channel pipeline) exit criteria met (GR-014: 91% lock rate on cert-watch full DAG, 20/22 items). Phase 3 adds multi-channel dispatch, per-role channel binding, and credential infrastructure.

**What exists:**
- 7-module runner: runner, gate, gate_process, router, scheduler, config, workspace
- 3 channel adapters: ClaudeCodeChannel, OpenCodeChannel (K2/GLM/DeepSeek via model selection), GeminiCLIChannel
- Multi-channel dispatch: runner selects channel per-role based on config binding
- Credential infrastructure: `~/.config/factory/credentials.yaml` for provider API keys
- 3 workflow YAMLs: phase1.yaml (single-role), phase2.yaml, phase3.yaml (3-stage pipeline)
- Spec lint integrated into `populate_work_items.py` (BC-127)
- 550 passing tests, 0 lint errors
- 19 golden runs executed (GR-001 through GR-019)
  - GR-019: 94% lock rate (15/16) on cert-watch full DAG, K2-only; zero ruff failures; inner gate first-attempt rate 64%
  - GR-015: 100% lock rate (24/24) on cert-watch full DAG, K2-only; 0% first-attempt pass rate (all required inner gate retry)
  - GR-014: 91% lock rate (20/22) on cert-watch full DAG with K2 via Fireworks

**Known issues:** 4 open breadcrumbs (0 critical, 2 high, 1 medium, 0 low) + 1 proposed (deferred to Phase 4) + 14 RFCs. See `breadcrumbs/README.md`.

**Blocking on:** nothing. All channels have adapter implementations.

**Phase 3 exit criteria** (defined in `spec.md` §10, must be met by a single clean golden run):
- First-attempt mechanical-gate pass rate ≥ 60%
- Lock-within-budget rate ≥ 90%
- Mean attempts to lock ≤ 2.0
- ≤1 stuck item per 16-work-item DAG
- ≤10% unknown/tool_not_found gate failures; ≥80% deterministic
- Spec lint wired and producing deterministic findings
- BC-126 analysis report exists with conclusion
- No breadcrumb status drift
- Default config binds only validated channels

**Next concrete steps before Phase 4:**
1. Run BC-126 Phase A measurement (work-item size vs first-attempt correlation)
2. Execute clean GR-020 to validate exit criteria
3. Fleet triage: validate or disable untested channels (Gemini, GLM, DeepSeek)
4. Add `mean_attempts_to_lock` telemetry dimension

## What not to build yet

The phasing in `spec.md` §10 exists to prevent the v1 mistake of building the whole architecture at once. Current constraints:
- Three-role pipeline only (interface_architect, test_author, implementer). Roles beyond these have no implementation.
- Mechanical gates only. Cross-family review, frontier jury, and coherence review are Phase 3-4.
- No jury gates or race patterns until Phase 4.
- Channel adapters for DeepSeek (standalone Ollama adapter) and Gemini (CLI has Node.js version issue on current host) exist but are not yet validated in golden runs.
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

The pipeline runs 3 concurrent processes (runner, gate, scheduler) against a PostgreSQL database and a real model channel.

### Prerequisites

- PostgreSQL running: `docker compose -f /projects/substrate/docker-compose.test.yml up -d`
- Model channel available. For `opencode` channel: `opencode` CLI must be in PATH (installed at `~/.opencode/bin/opencode`). Auth is handled internally by opencode — no `FIREWORKS_API_KEY` env var needed. Verify with `opencode run --dangerously-skip-permissions --model <model> --help`.

### Execution

```bash
# 1. Create config YAML (copy a prior golden-run-NNN-config.yaml, change project_name and workspace_root)
# 2. Populate work items from fixture (--workflow inferred from config)
make golden-run CONFIG=golden-run-019-config.yaml FIXTURES=tests/fixtures/cert-watch
# 3. This runs populate, then runner+gate+scheduler in parallel, then telemetry
```

For manual step-by-step control (recommended for monitoring):

```bash
.venv/bin/python populate_work_items.py --config golden-run-019-config.yaml --reset --fixtures tests/fixtures/cert-watch
.venv/bin/python -m factory.runner --config golden-run-019-config.yaml > /tmp/gr019-runner.log 2>&1 &
.venv/bin/python -m factory.gate_process --config golden-run-019-config.yaml > /tmp/gr019-gate.log 2>&1 &
.venv/bin/python -m factory.scheduler --config golden-run-019-config.yaml > /tmp/gr019-scheduler.log 2>&1 &
wait
.venv/bin/python -m factory.telemetry --config golden-run-019-config.yaml
.venv/bin/python -m factory.telemetry --verify --config golden-run-019-config.yaml
```

### Monitoring

Check progress while running:
```bash
tail -20 /tmp/gr019-runner.log
tail -10 /tmp/gr019-scheduler.log
tail -10 /tmp/gr019-gate.log
```

Processes are idle when no new log lines appear for >60s. Kill with `kill <PID>` or `kill -9 <PID>` if needed, then run telemetry.
