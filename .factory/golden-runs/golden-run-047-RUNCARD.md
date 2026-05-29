# GR-047 Run Card — MiMo decomposer on url-shortener (web-service archetype)

**Status:** complete — see `golden-run-047-log.md` (reconciled per BC-223)
**Config:** `.factory/golden-runs/golden-run-047-config.yaml`
**Decomposer:** MiMo-V2.5-Pro (`opencode` channel, model `xiaomi-token-plan-sgp/mimo-v2.5-pro`)
**Spec:** `tests/fixtures/url-shortener/spec.yaml`
**Workers/review/jury:** unchanged from GR-046 (K2 workers, Sonnet review+jury) — the workload shape is the ONLY variable
**XDG_DATA_HOME:** `/tmp/sf2-golden-047-xdg` (isolates opencode sessions from the principal's store)

---

## Why this run exists

GR-046 validated MiMo on dep-graph-viewer (CLI shape). GR-047 validates the pipeline on a **web-service** workload — HTTP handlers, Pydantic models, SQLite persistence, route definitions. This is the first non-CLI workload. If the pipeline handles it at ≥96% lock, that's real generalization evidence. If it doesn't, the failure modes tell us exactly where the pipeline is over-fitted to CLI archetypes.

## Session isolation

The opencode CLI stores session state in `$XDG_DATA_HOME/opencode/`. Setting it to a temp directory prevents golden-run sessions from appearing in the principal's session history.

```bash
export GR047_XDG=/tmp/sf2-golden-047-xdg
rm -rf "$GR047_XDG" && mkdir -p "$GR047_XDG"
```

## Step 1 — Decompose (fresh session) + populate

```bash
cd /projects/software-factory-2
export GR047_XDG=/tmp/sf2-golden-047-xdg
rm -rf "$GR047_XDG" && mkdir -p "$GR047_XDG"
rm -rf /tmp/sf2-golden-047
XDG_DATA_HOME="$GR047_XDG" .venv/bin/python populate_work_items.py \
  --config .factory/golden-runs/golden-run-047-config.yaml \
  --reset \
  --spec-yaml tests/fixtures/url-shortener/spec.yaml \
  --decomposer-channel opencode \
  --decomposer-model xiaomi-token-plan-sgp/mimo-v2.5-pro
```

## Step 2 — INSPECT decomposer output (HALT here)

```bash
ls -1 /tmp/sf2-golden-047/.decomposed/*.md
grep -rin "AC-LOG\|redact\|audit entry\|replacement type\|fr05\|FR-05" /tmp/sf2-golden-047/.decomposed/
```

Expect exactly 5 semantic modules mapping to FR-01..FR-05 (e.g. `link_creator`, `link_resolver`, `stats_tracker`, `link_lister`, `input_validator`). No log-redact-cli or dep-graph-viewer contamination.

## Step 3 — Launch pipeline (only if decomposition is clean)

```bash
export GR047_XDG=/tmp/sf2-golden-047-xdg
cd /projects/software-factory-2
XDG_DATA_HOME="$GR047_XDG" nohup .venv/bin/python -m factory.runner --config .factory/golden-runs/golden-run-047-config.yaml > /tmp/gr047-runner.log 2>&1 &
XDG_DATA_HOME="$GR047_XDG" nohup .venv/bin/python -m factory.gate_process --config .factory/golden-runs/golden-run-047-config.yaml > /tmp/gr047-gate.log 2>&1 &
XDG_DATA_HOME="$GR047_XDG" nohup .venv/bin/python -m factory.scheduler --config .factory/golden-runs/golden-run-047-config.yaml > /tmp/gr047-scheduler.log 2>&1 &
```

Monitor: `tail -f /tmp/gr047-runner.log /tmp/gr047-gate.log /tmp/gr047-scheduler.log`

## Step 4 — Telemetry

```bash
.venv/bin/python -m factory.telemetry --config .factory/golden-runs/golden-run-047-config.yaml
.venv/bin/python -m factory.telemetry --verify --config .factory/golden-runs/golden-run-047-config.yaml
```
