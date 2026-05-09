# GR006a Execution Plan — Cert-Watch FR-02 + FR-03 as Phase 2 Adversarial Fixture

**Status:** draft
**Author:** claude-opus-4-7
**Date:** 2026-05-09
**Origin:** Debate 008 (golden-run fixture representativeness) + cert-watch reference from `/projects/software-factory/projects/cert-watch/spec.md`

## Purpose

Settle the open Phase-2 exit question: do the curated 15-fixture pass rates from GR004 (91%) and GR005 (93%) generalize to fixtures with the characteristics of real line-of-business work? If yes, Phase 2 closes. If not, identify the gap before Phase 3 channel expansion compounds it.

This is **a measurement, not a feature.** The pipeline isn't being changed for it (with one prerequisite — see §Prerequisites). The fixture itself is the experiment.

## Scope

Two work-items derived from `cert-watch/spec.md` FR-02 and FR-03, sharing a third upstream interface_spec for the `Certificate` model. All three flow through the full 4-stage Phase 2 pipeline.

| WI | Type | Source | Why it stresses the pipeline |
|---|---|---|---|
| 1 | `interface_spec` (`Certificate` model) | Synthesized from cert-watch FR-02/03 shared types | Cross-work-item ref consumer; dataclass with non-trivial fields (DER bytes, issuer DN, SANs, validity window) |
| 2 | `interface_spec` → `test_suite` → `implementation` (FR-02: TLS scan) | cert-watch FR-02 spec | Real I/O at gate time (TCP socket + TLS handshake), error taxonomy (DNS, refused, timeout, expired, chain incomplete), depends on WI 1 |
| 3 | `interface_spec` → `test_suite` → `implementation` (FR-03: file upload + parse) | cert-watch FR-03 spec | Filesystem I/O, multi-format parse (PEM/DER/PKCS7), depends on WI 1 |

**Explicitly out of scope for GR006a:**
- FR-01 dashboard (UI — needs Debate 001's behavioral gate, deferred to GR006b)
- FR-04 email alerts (SMTP infra; not adversarial in an interesting new way)
- FR-05 daily scan (scheduler; orthogonal to pipeline correctness question)
- AC ambiguity (Phase 5 concern; would conflate the experiment)

## Pass criteria (signal, not pass/fail)

| Outcome | Interpretation | Action |
|---|---|---|
| ≥70% impl pass *and* recovery within retry budget on at least 2/3 items | Curated fixtures generalize to LoB-flavored fixtures | Phase 2 closes; proceed to Phase 3 |
| 40–70% impl pass | Generalizes partially; gap identifiable | Phase 2 closes; gap filed as Phase-3 monitoring item |
| <40% impl pass *or* a stage that simply cannot complete (e.g., gate can't import `cryptography`) | Curated fixtures don't generalize | Pause Phase 3; root-cause; consider intermediate fixtures |

The bar is intentionally lower than GR004/005's 80% because the fixtures are deliberately harder. A drop is expected; the size of the drop is the data.

## Prerequisites

These must land before GR006a runs. None are in current scope outside this plan unless flagged.

1. **BC-068 telemetry fix landed** (Debate 002).
   - Why blocking: GR006a's primary output is the per-(role, channel, gate) table. If gate names are `unknown`, the result is uninterpretable.
   - Estimated cost: 1 session.

2. **Per-project venv shim landed** (Debate 006, narrow scope).
   - Why blocking: cert-watch needs `cryptography` for FR-02 chain parsing and likely `httpx` or stdlib for TLS — none in the factory venv. Without the shim, every implementation gate fails on `ImportError` regardless of correctness.
   - Estimated cost: 1 session (~50–80 lines per Debate 006 position).

3. **Spec authoring (this plan).**
   - Three `spec.md`-style files in `tests/fixtures/cert-watch-mini/`: one per WI (Certificate model, FR-02, FR-03).
   - Translated from cert-watch's existing FR text into sf2's spec format (problem statement, acceptance criteria with AC IDs, glossary excerpt).
   - Estimated cost: 2–3 hours principal-driven authoring (or a dedicated agent session).

4. **Workflow + populate script.**
   - `golden-run-006-config.yaml` (channel: claude-code, sonnet — match GR004 baseline so the comparison is clean).
   - `populate_work_items.py` extension to load cert-watch-mini fixtures.
   - Verify: WI 1 is `interface_spec` only; WI 2 and WI 3 declare `interface_ref → WI 1`.

## Step-by-step execution

### Step 0 — Verify prerequisites (½ day)

- BC-068 fix merged; `make check` clean; telemetry replay-fixture test passing.
- `use_project_venv: true` flag working against a smoke fixture that imports a non-stdlib package.
- 295+ unit tests pass.

### Step 1 — Author cert-watch-mini fixtures (½ day)

For each WI, produce a spec file mirroring cert-watch's FR text, but adapted to sf2's spec format:

- **WI 1 — `Certificate` model spec.** ~5 ACs covering: required fields (subject DN, issuer DN, NotBefore, NotAfter, SANs, fingerprint_sha256, raw DER), validity computation (`days_until_expiry`), equality/hashing semantics, parse from DER bytes, error type for malformed input.

- **WI 2 — FR-02 spec.** ~6 ACs from cert-watch FR-02 + the "scanned entry" glossary term. Required behaviors: connect to host:port with timeout, complete TLS handshake, extract leaf + intermediate certs, normalize each into a `Certificate`, handle DNS failure / connection refused / timeout / expired / partial chain. Declare `interface_ref: certificate_model` (WI 1).

- **WI 3 — FR-03 spec.** ~5 ACs from cert-watch FR-03. Required behaviors: parse PEM, parse DER, parse PKCS7, error on malformed, return ordered chain (leaf first), handle unicode in subject/issuer DNs. Declare `interface_ref: certificate_model` (WI 1).

Save under `tests/fixtures/cert-watch-mini/`. Commit.

### Step 2 — Run pipeline against cert-watch-mini (1 hour wall-clock + monitoring)

```bash
# Reset workspace and project
python populate_work_items.py --reset --project sf2_gr006a --fixtures tests/fixtures/cert-watch-mini

# Launch worker, gate, scheduler with claude-code Sonnet
python -m factory.runner --config golden-run-006-config.yaml \
    --workspace /tmp/sf2-gr006a > /tmp/gr006a-runner.log 2>&1 &
python -m factory.gate_process --config golden-run-006-config.yaml \
    --workspace /tmp/sf2-gr006a > /tmp/gr006a-gate.log 2>&1 &
python -m factory.scheduler --config golden-run-006-config.yaml \
    > /tmp/gr006a-scheduler.log 2>&1 &
```

Monitor via existing tooling (whatever was used in GR004/005 — likely `watch` over `query_work_items`).

Expected wall-clock: 30–60 min for 3 work-items (cert-watch ACs are denser than the curated fixtures, so per-item time should be higher than GR004's average).

### Step 3 — Capture results (½ day)

Produce `golden-run-006a-log.md` mirroring GR004/005 log structure:

- Timeline (T+0 / T+10m / etc.)
- By-stage table (interface_spec / test_suite / implementation, locked / cannot_proceed / in_progress)
- Per-WI escalation reasons (if any), with the actual gate diagnostic that fired
- Telemetry table (this is the key output — must show real gate names per BC-068 fix)
- Wall-clock comparison to GR004
- Failure mode analysis: what *kind* of failure, was it pipeline / gate / model / fixture?

### Step 4 — Decide (immediate, principal-led)

Apply the pass-criteria table at the top of this doc. Three possible decisions:

- **Close Phase 2.** Update `phase2-implementation.md` exit-criteria status; open Phase 3 RFC; archive plan.
- **Close Phase 2 with monitoring.** Same, plus file a breadcrumb naming the specific gap (e.g., "TLS-error taxonomy not handled cleanly by gates") to track during Phase 3.
- **Pause Phase 3.** File a breadcrumb describing the failure mode; do not start channel expansion until root-caused. May require additional intermediate fixtures.

### Step 5 — Record fixture for replay (1 hour)

Regardless of outcome, archive event dump + artifacts to `tests/fixtures/golden-run-006a/`. Add `tests/test_golden_run_006a.py` replay test using `MockChannel` + `MockSubstrate`. This becomes part of the Phase 3 regression baseline.

## Risks

| Risk | Mitigation |
|---|---|
| `cryptography` lib subprocess gate is slow (compile + import) | Pre-install in the project venv during Step 0 verification; cache venv |
| TLS gates require network access; CI may not have it | Run GR006a locally only; do not gate CI on it. Replay test (Step 5) uses fixtures, no network |
| Cert-watch FR ACs are vaguer than curated fixtures, producing high `cannot_proceed` rate at interface_architect | This *is* the experiment. If interface_architect can't synthesize a usable contract from FR-style ACs, that's a Phase 2 finding. Don't sharpen the ACs to make it pass |
| 1 hour of Sonnet at GR-002 token rates | Acceptable — within experimental budget. Rough estimate ~$5–10 |
| Sonnet's first-attempt impl pass rate on cert-watch is meaningfully lower than the 80% curated baseline (entirely possible) | That's the data. Lower is informative |

## Out of scope (explicit)

- Per-cert-watch-FR refactoring of sf2 itself
- Gemini / DeepSeek / GLM channels (Phase 3)
- Behavioral validation (deferred to GR006b)
- AC-ambiguity testing (deferred to GR006b)
- Performance / scale (3 work-items only)

## Deliverables

1. `tests/fixtures/cert-watch-mini/` — three spec files committed
2. `golden-run-006-config.yaml` committed
3. `golden-run-006a-log.md` written
4. `tests/fixtures/golden-run-006a/` — event dump + artifacts
5. `tests/test_golden_run_006a.py` — replay regression test
6. Phase-2 exit decision recorded in `phase2-implementation.md` and worklog

## Estimated total

~2 days end-to-end (½ prerequisites + ½ authoring + ½ run + ½ analysis & recording), assuming BC-068 and venv shim already done. If those two prerequisites are bundled, add 2 sessions.
