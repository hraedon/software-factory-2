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

**Phase 4 (jury and review skeleton validated, first golden run pending).** Phase 3 exit criteria met (GR-021). Phase 4 adds cross-family review and frontier jury gates to the pipeline, enabled by `phase4.yaml` (v4 workflow) and the `jury` / `review` modules.

**What exists:**
- 7-module runner: runner, gate, gate_process, router, scheduler, config, workspace
- 3 channel adapters: ClaudeCodeChannel, OpenCodeChannel (K2/GLM/DeepSeek via model selection); GeminiCLIChannel disabled (unvalidated)
- Multi-channel dispatch: runner selects channel per-role based on config binding
- Credential infrastructure: `~/.config/factory/credentials.yaml` for provider API keys
- 5 workflow YAMLs: phase1.yaml, phase2.yaml, phase3.yaml, phase4.yaml (review + jury), full_pipeline.yaml
- Spec lint integrated into `populate_work_items.py` (BC-127)
- 599 passing tests, 0 lint errors
- 22 golden runs executed (GR-001 through GR-022)
  - GR-022: Phase 4 first run — 100% lock rate (15/15) on cert-watch-mini, all 5 roles exercised (interface→tests→impl→review→jury), single-family jury, 50 min wall clock
  - GR-021: 100% lock rate (24/24) on cert-watch full DAG, K2-only; inner gate first-attempt rate 74% (20/27); wrong_module_name feedback: 5/5 recovered on retry=1
  - GR-020: 100% lock rate (24/24) on cert-watch full DAG, K2-only; zero ruff failures; inner gate first-attempt rate 77% (20/26)

**Known issues:** 2 open breadcrumbs (0 critical, 0 high, 1 medium, 0 low) + 1 proposed (deferred to Phase 4) + 18 RFCs. See `breadcrumbs/README.md`.

**Blocking on:** nothing. All validated channels have working adapters; unvalidated adapters disabled.

**Phase 3 exit criteria** (defined in `spec.md` §10, must be met by a single clean golden run):
- First-attempt mechanical-gate pass rate ≥ 60% — **met via inner gate: 74% (GR-021)**
- Lock-within-budget rate ≥ 90% — **met: 100% (GR-021)**
- Mean attempts to lock ≤ 2.0 — **met: 1.08 (GR-021)**
- ≤1 stuck item per 16-work-item DAG — **met: 0 stuck (GR-021)**
- ≤10% unknown/tool_not_found gate failures; ≥80% deterministic — **met: 0% unknown; deterministic rate includes composite gate names**
- Spec lint wired and producing deterministic findings — **met**
- BC-126 analysis report exists with conclusion — **met** (`.factory/analysis/2026-05-13-work-item-granularity.md`)
- No breadcrumb status drift — **met**
- Default config binds only validated channels — **met** (GeminiCLIChannel disabled; implementer uses K2)

**Next concrete steps (Phase 4 validation):**
1. ✅ Execute Phase 4 golden run (GR-022) against `cert-watch-mini` with `phase4.yaml` — **done; 100% lock rate, all 5 roles exercised**
2. 🔄 Run multi-family jury GR with `jury_quorum=2` and ≥2 distinct channel families
3. 🔄 Exercise review rejection + retry path (may need synthetic test)
4. 🔄 Exercise jury disagreement/quorum-not-met path

## What not to build yet

The phasing in `spec.md` §10 exists to prevent the v1 mistake of building the whole architecture at once. Current constraints:
- Five-role pipeline (interface_architect, test_author, implementer, cross_family_reviewer, frontier_judge). Roles beyond these (integrator, outcome_verifier, coherence_reviewer) have no implementation.
- Mechanical gates + single-channel review/jury gates. Multi-family jury racing is validated in skeleton but awaiting first golden-run exercise.
- No integration or outcome-verification stages until Phase 5.
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
