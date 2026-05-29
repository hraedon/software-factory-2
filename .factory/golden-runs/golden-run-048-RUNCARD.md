# GR-048 Run Card — url-shortener re-run, 3-member jury (K2 + Sonnet + MiMo), artifacts preserved

**Status:** complete — see `golden-run-048-log.md`
**Config:** `.factory/golden-runs/golden-run-048-config.yaml`
**Decomposer:** MiMo-V2.5-Pro (`opencode`, `xiaomi-token-plan-sgp/mimo-v2.5-pro`)
**Spec:** `tests/fixtures/url-shortener/spec.yaml` (same web-service fixture as GR-047)
**Workers:** K2 (opencode) — unchanged from GR-047
**Reviewer:** Sonnet (claude-code) — unchanged from GR-047
**Jury:** **3-member panel, quorum 2** — K2 (opencode) + Sonnet (claude-code) + MiMo (opencode)
**XDG_DATA_HOME:** `/tmp/sf2-golden-048-xdg`

---

## Why this run exists

GR-047 (first web-service workload) locked only 88%: 2 of 4 modules escalated to `cannot_proceed` on a K2/Sonnet **jury disagreement**, despite 100% inner-gate first-pass and 100% review pass. The GR-047 log framed this as "the jury working as designed, catching genuine architectural uncertainty" — but **never inspected the verdicts** to confirm the disagreement was substantive rather than stylistic, and the artifacts were then deleted. The load-bearing question is unanswered:

> Is the jury a real defense (it found genuine architectural problems and correctly refused to ship), or a false-reject (two models with different tastes for HTTP-handler/Pydantic/route layout, blocking correct software)?

That distinction is decisive. If false-reject, the jury over-fires on unfamiliar archetypes and the "pipeline generalizes" claim is weaker than stated — a high-severity, silent failure-to-ship. If genuine, the framing holds.

## Design — what changed from GR-047 and why

- **Only the jury composition changes.** Decomposer (MiMo), workers (K2), and reviewer (Sonnet) are held identical to GR-047 so the jury is the single variable.
- **3-member jury, quorum 2.** GR-047's K2+Sonnet pair is reproduced for comparability, and **MiMo is added as a third, independent voice**. With quorum 2, the previously-uninformative 1-1 deadlock becomes a decision we can read:
  - MiMo agrees with the **pass** vote → 2/3 pass → item **locks**; the GR-047 block was a 1-of-3 minority position → **false-reject evidence**.
  - MiMo agrees with the **block** vote → votes_for = 1 < 2 → `cannot_proceed`; now **two independent models** object → **real-concern evidence**.
- **`--no-cleanup` is mandatory.** The entire point is to read the per-juror rationales. Do **not** run without it.

**Leaner alternative (if the principal prefers minimal spend):** drop to a 2-member jury by removing one of the K2/Sonnet roles, leaving the partner + MiMo. This loses the tiebreak reading and reduces to "did swapping that one juror change the verdict." The 3-member panel is preferred because it answers the real-vs-false question directly in one run.

## Folded-in forensic — BC-222 (outcome_e2e on web services)

GR-047 also had one unexplained `outcome_e2e` escalation + one orphan submit (BC-222). Because this run preserves artifacts, capture the outcome-verification forensics here too:
- If an `outcome_e2e` item escalates, inspect the gate subprocess: did the uvicorn/FastAPI server start? did the health-probe race the port bind? did teardown leak a process?
- Reproduce the gate command with both `.venv/bin/python` and the workspace `.venv-gate/bin/python` (BC-174 protocol).
- If it's a server-lifecycle handling gap, append a row to CLASS-008 and update BC-222 with the confirmed root cause.

## Session isolation

```bash
export GR048_XDG=/tmp/sf2-golden-048-xdg
rm -rf "$GR048_XDG" && mkdir -p "$GR048_XDG"
```

## Step 1 — Decompose (fresh session) + populate

```bash
cd /projects/software-factory-2
export GR048_XDG=/tmp/sf2-golden-048-xdg
rm -rf "$GR048_XDG" && mkdir -p "$GR048_XDG"
rm -rf /tmp/sf2-golden-048
XDG_DATA_HOME="$GR048_XDG" .venv/bin/python populate_work_items.py \
  --config .factory/golden-runs/golden-run-048-config.yaml \
  --reset \
  --spec-yaml tests/fixtures/url-shortener/spec.yaml \
  --decomposer-channel opencode \
  --decomposer-model xiaomi-token-plan-sgp/mimo-v2.5-pro
```

## Step 2 — INSPECT decomposer output (HALT here)

```bash
ls -1 /tmp/sf2-golden-048/.decomposed/*.md
grep -rin "AC-LOG\|redact\|audit entry\|AC-DGV\|graph\|fr05\|FR-05" /tmp/sf2-golden-048/.decomposed/
```

Expect semantic modules mapping to url-shortener FRs (e.g. `link_creator`, `link_resolver`, `link_lister`, `error_formatter`). No log-redact-cli or dep-graph-viewer contamination (BC-220).

## Step 3 — Launch pipeline (only if decomposition is clean)

Prefer the supervised wrapper (BC-140 protocol), and **keep the workspace**:

```bash
cd /projects/software-factory-2
.venv/bin/python scripts/agent_golden_run.py \
  --config .factory/golden-runs/golden-run-048-config.yaml \
  --fixtures tests/fixtures/url-shortener \
  --log-prefix gr048 \
  --no-cleanup
```

(Manual launch is acceptable if the wrapper does not support `--spec-yaml` decomposition; if launching manually, set `XDG_DATA_HOME="$GR048_XDG"` on every process and do not delete `/tmp/sf2-golden-048`.)

## Step 4 — Telemetry

```bash
.venv/bin/python -m factory.telemetry --config .factory/golden-runs/golden-run-048-config.yaml
.venv/bin/python -m factory.telemetry --verify --config .factory/golden-runs/golden-run-048-config.yaml
```

## Step 5 — Read the jury verdicts (the point of this run)

For every jury work item, read the preserved verdict artifact and record, per item:

```bash
find /tmp/sf2-golden-048 -name 'jury_verdict*.json' -o -name '*jury*verdict*' 2>/dev/null
# For each: votes_for / votes_against, quorum_met, and each juror's pass + rationale.
```

For each item that disagreed in GR-047, answer in the log:
- How did each of K2 / Sonnet / MiMo vote, and **what specifically** did the dissenter object to?
- Was the objection a correctness/architecture concern (real) or a style/layout preference (false-reject)?
- Did MiMo's vote move the item to lock (false-reject evidence) or keep it blocked (real-concern evidence)?

State the verdict-adjudication conclusion explicitly. If the disagreements are stylistic, file a BC against the jury rubric (over-firing on unfamiliar archetypes) — do **not** repeat GR-047's "working as designed" framing without the per-juror evidence to support it.

## Step 6 — Write the log + commit

Create `golden-run-048-log.md` per the AGENTS.md format. Required, in addition to the standard sections:
- **Jury adjudication** section with the per-item, per-juror table and the real-vs-false-reject conclusion.
- **BC-222 outcome_e2e forensics** (if an escalation occurred): confirmed root cause or "no escalation this run."
- Update this runcard's `Status:` to `complete` (per BC-223), then commit config + log together.
