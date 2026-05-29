# GR-046 Run Card — MiMo decomposer on dep-graph-viewer, fresh session

**Status:** not yet run — prepared for handoff
**Config:** `.factory/golden-runs/golden-run-046-config.yaml`
**Decomposer:** MiMo-V2.5-Pro (`opencode` channel, model `xiaomi-token-plan-sgp/mimo-v2.5-pro`)
**Spec:** `tests/fixtures/dep-graph-viewer/spec.yaml`
**Workers/review/jury:** unchanged from GR-044/045 (K2 workers, Sonnet review+jury) — the decomposer is the ONLY variable
**References:** W5 decision gate addendum (`plans/2026-05-28-w5-decision-gate.md`), BC-220, GR-043, GR-045

---

## Why this run exists

The W5 gate's "Phase B validated on N=2 workloads" rests on a confound: MiMo decomposed log-redact-cli (GR-043, clean) and **Sonnet** decomposed dep-graph-viewer (GR-045, contaminated — BC-220). No single decomposer model has been validated across both workloads. GR-046 runs **MiMo on dep-graph-viewer** — the run that was actually planned in GR-043 lesson #5 — to get one model clean across both, and to test whether BC-220's contamination is session-driven or model-driven.

## What is actually being measured

**Primary measurement = the raw decomposer output, not the lock rate.** The whole point is the BC-220 question. Inspect the decomposer output BEFORE caring about the pipeline.

**Secondary measurement = full-pipeline lock rate** (only if the decomposition is clean and worth running through).

## The one control that makes the result interpretable: FRESH SESSION

BC-220's root-cause hypothesis is that Sonnet leaked log-redact-cli content because the dep-graph-viewer decomposition ran in a session/context that had **already decomposed log-redact-cli**. If GR-046 reuses such a session, a contaminated result tells you nothing.

**Control:** point opencode at a fresh, empty session store via `XDG_DATA_HOME`, and do NOT decompose any other spec in that store first. MiMo runs on the `opencode` channel, whose session DB lives under `$XDG_DATA_HOME/opencode`. A fresh empty dir = a clean session.

```bash
export GR046_XDG=/tmp/sf2-golden-046-xdg
rm -rf "$GR046_XDG" && mkdir -p "$GR046_XDG"   # guarantee no prior decomposition in this store
```

## Prerequisites (verify before launch)

1. Postgres up: `docker compose -f /projects/regista/docker-compose.test.yml up -d`
2. Channel health: confirm MiMo (`xiaomi-token-plan-sgp/mimo-v2.5-pro`) and K2 reachable on opencode, and claude-code (Sonnet) healthy. GR-042's 69% was a channel-health failure — do not skip this.
3. Run from repo root (`/projects/software-factory-2`); opencode needs project context.

## Step 1 — Decompose (fresh session) + populate

`populate_work_items.py` with `--spec-yaml` decomposes AND populates in one shot, writing the decomposer output to `<workspace_root>/.decomposed/`. Run it under the fresh `XDG_DATA_HOME`:

```bash
cd /projects/software-factory-2
export GR046_XDG=/tmp/sf2-golden-046-xdg
rm -rf "$GR046_XDG" && mkdir -p "$GR046_XDG"
XDG_DATA_HOME="$GR046_XDG" .venv/bin/python populate_work_items.py \
  --config .factory/golden-runs/golden-run-046-config.yaml \
  --reset \
  --spec-yaml tests/fixtures/dep-graph-viewer/spec.yaml \
  --decomposer-channel opencode \
  --decomposer-model xiaomi-token-plan-sgp/mimo-v2.5-pro
```

## Step 2 — INSPECT decomposer output (this is the primary result) — HALT here

No pipeline work happens until the runner/gate/scheduler launch, so stop and inspect:

```bash
ls -1 /tmp/sf2-golden-046/.decomposed/*.md
grep -rin "AC-LOG\|redact\|audit entry\|replacement type\|rule scope\|fr05\|FR-05" /tmp/sf2-golden-046/.decomposed/
```

Record, explicitly:
- **Module count and names.** Expect exactly 4 semantic modules mapping to FR-01..FR-04 (e.g. `event_log_reader`, `graph_builder`, `graph_filter`, `dot_emitter`). dep-graph-viewer has only 4 FRs.
- **Contamination check (the BC-220 question):** any `wi_fr05.md`, any `AC-LOG-*` IDs, any log-redact-cli glossary terms (audit entry, redaction rule, replacement type, rule scope, structured log), any `wi_frNN.md` Phase-A fallback files sitting alongside semantic-named files.

**Do NOT hand-clean the output to "make it pass."** If MiMo contaminated, that contamination IS the finding — capture it verbatim and go to the contaminated branch below.

## Step 3 — Launch pipeline (only if decomposition is clean)

Use the same launch procedure as GR-045 (manual runner/gate/scheduler against this config), since `agent_golden_run.py`'s `_populate` does not drive `--spec-yaml` decomposition (GR-043 lesson #6) — the decompose was already done manually in Step 1. Launch the three processes from repo root, preserve logs, and let it run to idle (~20–40 min based on GR-044/045).

Capture the standard metrics table (lock-within-budget, mean attempts, first-gate pass, inner-gate first-pass, cannot_proceed, deterministic gate rate, orphan/unknown gate counts, verify_passed) in a `golden-run-046-log.md` matching the GR-044/045 format, with a comparison column against GR-043 (MiMo/log-redact) and GR-045 (Sonnet/dep-graph).

## Decision criteria → feeds the W5 addendum

| Decomposer output | Meaning | Action |
|---|---|---|
| **Clean** (4 semantic modules, no contamination) + pipeline ≥96% lock | MiMo validated across BOTH workloads; contamination looks **session-specific** (supports BC-220 workaround) | W5 RFC-023 promotion is on firm ground. Note BC-220 as session-hygiene, not model defect. |
| **Contaminated** (FR-05 / AC-LOG / extra modules) | BC-220 is **systemic across decomposer models**, not a Sonnet quirk | Promotion BLOCKED. Raise BC-220 severity above `medium`; the per-invocation context-isolation fix becomes a prerequisite, not an optional mitigation. |
| Clean decomposition but pipeline <96% lock | Decomposition fine, reliability regression elsewhere | Triage as a normal run failure (channel vs model vs pipeline), separate from the Phase B question. |

## Scope notes for whoever runs this

- This is still **N=1 for MiMo on dep-graph-viewer** — an existence proof, not a track record. Do not let a clean GR-046 get written up as "Phase B proven."
- GR-046 answers "does Phase B generalize safely," NOT "is semantic naming worth the complexity." GR-045 already found the names are a readability gain, not a correctness gain (no lock-rate lift over Phase A). That cost/benefit question stays open regardless of GR-046.
- Optional follow-up **GR-047:** re-run Sonnet on dep-graph-viewer in a *fresh* session to confirm BC-220 was the session artifact it hypothesizes. Lower priority than GR-046; only fully separates model-quality from session-hygiene.
