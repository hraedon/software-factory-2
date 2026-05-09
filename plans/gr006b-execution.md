# GR006b Execution Plan — Full Cert-Watch as Phase 5 Pre-Flight

**Status:** draft (deferred until Phase 5 trigger)
**Author:** claude-opus-4-7
**Date:** 2026-05-09
**Origin:** Debate 008 + Debate 001 (behavioral gate) + cert-watch reference from `/projects/software-factory/projects/cert-watch/spec.md`

## Purpose

Validate that sf2 can take a real, complete LoB project — full cert-watch with UI, scheduler, email, the works — from spec to running software through the multi-channel fleet. This is the **Phase 5 readiness experiment.** It is *not* the same experiment as GR006a, even though the project is the same.

Where GR006a asks "does the Phase 2 pipeline generalize beyond curated fixtures?", GR006b asks "is the full sf2 system ready for a real workload?" Different question, different gates required, different success criteria, different blast radius.

## When to trigger

GR006b runs only when **all** of the following are true:

1. Phase 3 (fleet integration) is complete — at least 3 channels (claude-code, opencode, K2 or GLM) have validated golden runs.
2. Phase 4 (jury gates + cross-family review) is complete — frontier judge produces non-trivial signal on at least one prior GR.
3. Debate 001 (behavioral / Playwright gate) is implemented — even minimally.
4. Per-project venv (Debate 006) is on by default.
5. Credentials infrastructure (Debate 007) handles whatever providers are participating.
6. GR006a closed cleanly (or with documented gaps that are now addressed).

If any of these is missing, **do not run GR006b.** Running it early reproduces v1's mistake: real workload through a half-built pipeline produces 11 partial cert-watch attempts and no learning.

## Scope

The full cert-watch v1 spec (`/projects/software-factory/projects/cert-watch/spec.md` §4 FR-01 through FR-05), decomposed into work-items at FR granularity. Approximate decomposition:

| WI Group | FR | New work-items | Notes |
|---|---|---|---|
| Models | — | 3 (Certificate, MonitoredEntry, AlertConfig) | Foundational types, no FR mapping |
| Storage | — | 2 (Repository protocol + SQLite impl) | Stateful; Repository pattern per spec.md §5 |
| Scanning | FR-02 | 2 (TLS scanner + scan service) | Reuses GR006a's Certificate model |
| Upload | FR-03 | 2 (file parser + upload handler) | Reuses GR006a's Certificate model |
| Alerts | FR-04 | 2 (SMTP sender + alert scheduler logic) | New territory |
| Scheduler | FR-05 | 1 (APScheduler integration) | New territory |
| Web | FR-01 | 3 (FastAPI app + dashboard route + sort/color logic) | UI — requires behavioral gate |
| Wiring | — | 1 (composition root) | Brings the above together |

Total: ~16 work-items, comparable in count to GR004/005's 15 fixtures but with real interdependencies and integration surface.

**Explicitly in scope for GR006b that wasn't in GR006a:**
- Cross-work-item state (database, shared models)
- Web UI exercised by behavioral gate
- AC ambiguity (FR-04's "configurable thresholds" intentionally underspecified)
- Multi-channel fleet (use Phase 3 placement)
- Jury / frontier judge if available
- End-to-end execution: the assembled system must actually *run* and *do the thing* (Stage 9 outcome verification)

## Pass criteria

GR006b is the first run where pass/fail genuinely matters because the output is intended to be deployable software, not pipeline measurement.

| Outcome | Interpretation | Action |
|---|---|---|
| All 16 WIs locked, behavioral gate passes for FR-01, end-to-end smoke (start app, scan a real cert, upload a PEM, alert fires) all green | sf2 is Phase-5 ready | Declare Phase 5 ready; cert-watch becomes a real maintained example |
| ≥80% WIs locked, but assembled software has correctness gaps caught only by behavioral gate or smoke | Gates need tightening; specific failure modes go to breadcrumbs | Patch gates; consider GR006c with same fixture |
| <80% WIs locked, OR assembled software fails to start, OR behavioral gate flags structural correctness issues that mechanical gates missed | Phase 5 not ready | File breadcrumbs; do not declare ready; root-cause |

## Prerequisites

In addition to Phases 3 and 4 being complete:

1. **`tests/fixtures/cert-watch-full/` authored.** Per-WI spec files derived from cert-watch v1 spec.md. Each WI declares its interface_refs and acceptance criteria. The `populate_work_items.py` script understands the link graph. Estimated cost: 1–2 days authoring.

2. **Behavioral gate implemented.** Per Debate 001 — at least Playwright + a minimal scenario format that lets FR-01's dashboard be exercised end-to-end (open page, verify cert list renders, sort works, color coding matches thresholds). Estimated cost: tracked in Phase 5 plan.

3. **Stage 9 outcome verification scaffolding.** sf2 must be able to actually run the assembled software (`uvicorn` start, scan a known cert, query the dashboard). This is per-spec but hasn't been built yet. Estimated cost: tracked in Phase 5 plan.

4. **Database fixture management.** SQLite teardown/setup between attempts. The repository pattern handles this in code, but the gate process needs an isolated DB per attempt. Per-attempt tempdir extension to `_run_pytest`. Small but real.

5. **Credentials configured for chosen multi-channel placement.** Per Debate 007. Whatever fleet placement Phase 3 validated.

6. **Multi-WI link-aware scheduler.** The current scheduler handles single-source `derived_from` and `tested_by` links. cert-watch has WIs depending on 2–3 upstream models. Confirm the scheduler handles fan-in. If not, that's a separate prerequisite breadcrumb.

## Step-by-step execution

### Step 0 — Trigger verification (½ day)

Confirm all six trigger conditions and all six prerequisites. Stop if any are missing. **This is the most important step.** GR006b run prematurely produces low-information failure.

### Step 1 — Author full cert-watch-full fixtures (1–2 days)

For each of the ~16 WIs, produce a spec file. Source: cert-watch v1 spec, decomposed at FR + supporting-type granularity. Each spec includes:

- Problem statement (1–3 sentences)
- 4–8 acceptance criteria with AC IDs
- Glossary excerpt
- `interface_ref` declarations to upstream WIs
- For FR-01: `behavioral_scenarios[]` block consumed by the behavioral gate
- For FR-04: at least one AC intentionally vague ("configurable thresholds" — does this mean per-cert? per-installation? per-cert-type?) — tests the orchestrator's clarification capability if present, or escalation if not

### Step 2 — Pre-flight smoke against single FR (½ day)

Before running all 16, run *just* the storage WIs (3 models + 2 repository) end-to-end. This validates: cross-WI links, fan-in scheduling, venv handles SQLite, gates handle a stateful contract. If this smoke fails, full GR006b will fail more expensively. Triage and fix the smoke before proceeding.

### Step 3 — Full GR006b run (3–6 hours wall-clock)

Launch with multi-channel placement chosen from Phase 3 data. Monitor live via mission-control-equivalent (whatever exists at that point — possibly still just `watch query_work_items`). Expected wall-clock substantially higher than GR004/005 because:

- 16 WIs vs 15
- Interdependencies serialize some work
- Behavioral gate is slow per Luke's data ("most of the mission's wall clock time is spent here waiting for real-world execution")
- Outcome verification (Stage 9) actually runs the software

### Step 4 — Outcome verification (½ day)

After all WIs lock, the composition root is run. Verify by external probe (not by the same models that wrote the code):

- `uvicorn cert_watch.app:app --port 8765`, then `curl http://localhost:8765/` returns the dashboard
- POST to `/scan` with a real hostname (e.g., `google.com:443`) returns extracted certs
- POST to `/upload` with a known-good PEM file creates a monitored entry
- A test cert near expiry triggers the alert path (with SMTP captured by a local fake)

This is **adversarial** validation per Luke's principle: the validators have not seen the code. Use a different model (or a deterministic script) for these probes.

### Step 5 — Write up (1 day)

Produce `golden-run-006b-log.md` covering all of the above plus:

- Per-WI cost (tokens × $/token by channel)
- Wall-clock breakdown by stage and by FR group
- Behavioral gate findings (screenshots, DOM diagnostics)
- Outcome-verification findings (what worked, what didn't)
- Comparison to v1 cert-watch attempts (which version is this comparable to? where did v1 land vs sf2?)

### Step 6 — Decide Phase 5 readiness (principal-led)

Apply the pass-criteria table. Three outcomes; the action paths are documented above.

### Step 7 — Archive

`tests/fixtures/golden-run-006b/` event dump + artifacts. `tests/test_golden_run_006b.py` replay test.

## Risks

| Risk | Mitigation |
|---|---|
| Behavioral gate is the largest unknown; likely 2× wall-clock vs estimate | Plan for 8h wall-clock; commit to a kill threshold (e.g., 12h) |
| Multi-channel coordination introduces failures GR006a couldn't see | This is part of the experiment; don't paper over |
| Stage 9 outcome verification doesn't exist yet | Listed as prerequisite; if it can't be built, skip that step and acknowledge GR006b is incomplete |
| Real cert-watch may need third-party deps that don't install in the venv (e.g., compiled extensions) | Test the venv setup against cert-watch's `pyproject.toml` *before* running GR006b |
| Costs higher than prior GRs (3–6h × multi-channel × 16 WIs) | Set a budget cap upfront ($50?); kill the run if cap exceeded; the kill is itself data |
| Fixtures take longer to author than estimated | Acceptable — fixture authoring is one-time investment that supports later regression testing |
| Result is ambiguous (some WIs pass, some fail in unexpected ways) | This is the *most likely* outcome. The post-run analysis is at least as important as the run itself; budget accordingly |

## Why GR006b is a *separate* plan from GR006a

GR006a and GR006b answer different questions. Bundling them risks a common v1 mistake: conflating "is the pipeline done?" with "is the system done?" These have different success criteria and different remediation paths. Keeping them separate means:

- GR006a's outcome doesn't gate on Phase 3/4 work
- GR006b's outcome doesn't reflect a still-evolving pipeline
- The cert-watch fixture investment is reused but the experiments are independently interpretable

## Deliverables

1. `tests/fixtures/cert-watch-full/` — ~16 spec files
2. `golden-run-006b-config.yaml`
3. `golden-run-006b-log.md`
4. `tests/fixtures/golden-run-006b/` — event dump + artifacts
5. `tests/test_golden_run_006b.py` — replay regression
6. Working cert-watch deployment (the *artifact* — sf2's first real LoB output)
7. Phase 5 readiness decision recorded

## Estimated total

~5–8 days of focused work once trigger conditions are met, dominated by fixture authoring (1–2d) and post-run analysis (1–2d). Run time itself is 3–6h. Plan for the analysis.
