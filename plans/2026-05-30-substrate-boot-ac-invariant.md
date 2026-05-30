# Plan: Substrate boot-AC invariant (GR-050 blocker → GR-051)

> **Status:** proposed, scoped to the url-shortener workload (one variable).
> **Lineage:** RFC-039 (deliverable decomposition + walking skeleton), RFC-038
> (verification-driven conformance gate / boot probe), RFC-030 (promote to an
> invariant, don't carve a per-symptom exception).
> **Author:** opus review session, 2026-05-30.

## Context — the blocker

GR-050 ran the Phase C deliverable decomposer for the first time. It correctly
identified the shared-infrastructure module `link_store` (SQLite schema + app
factory) and emitted it with `ac_ids: []`. The pipeline requires ≥1 AC to
validate any module: `spec_lint.check_ac_section_exists` returns an ERROR (and
`spec_lint` early-returns) when a spec has no AC section, and
`check_ac_count_within_band` ERRORs on `<1` AC. So `link_store` went
`cannot_proceed` and the DAG stalled at 80% lock on a single-point-of-failure
substrate.

The decomposer prompt *permits* empty `ac_ids` for substrate, but the pipeline
has no mechanism to validate an AC-less module. GLM surfaced three options:
1. assign a walking-skeleton AC to substrates (in the decomposer prompt);
2. bypass AC validation for infrastructure modules;
3. merge substrate into the first dependent module.

## Decision

**Adopt Option 1 as an invariant — strengthened so the AC is system-attached
and discharged by the RFC-038 boot probe, not authored by the decomposer.**
Keep Option 3 as the single-dependent degenerate case. **Reject Option 2.**

- **Why not Option 2:** an AC-less, validation-skipped module is unverified
  code in the artifact — the exact "verify by reading, not running" hole
  RFC-039 exists to close — and the substrate is the highest-leverage place to
  allow it (every slice imports it; GR-050's 80% stall was the substrate taking
  everything down). It also recreates GR-048 (nothing owned/verified the shared
  layer → `link_creator` used real sqlite while `link_lister` fabricated data),
  and per RFC-030 a category-wide bypass is precisely the per-symptom escape
  hatch the block rule forbids.
- **Why system-attached, not "add it in the decomposer prompt":** asking the
  model to author its own gate criterion is a soft spot (vacuous ACs). The boot
  AC is owned by the pipeline and discharged by execution, so the model never
  writes it and can't weaken it.
- **Why Option 3 stays:** when a substrate has exactly one dependent, inlining
  it is cleaner than a ceremonial separate module, and its correctness is
  covered transitively by that slice's real ACs.

## Terminology — read before implementing ("substrate" is overloaded)

- **sf2 decomposer "substrate module"** — the shared-infrastructure module
  *inside the generated artifact* (app factory + DB schema + shared models) that
  vertical slices import. This is GR-050's `link_store`. **This plan governs
  only this sense.**
- **regista** (the library, **renamed from `substrate` on 2026-05-27**) — the
  durable-state/coordination layer sf2 itself runs on, and the likely
  shared-state backend for *real* generated workloads.

These are different layers; do not conflate them in code or naming. Use a
precise identifier — `is_shared_substrate` / "skeleton substrate module" — not
bare "substrate", to avoid the regista collision. The overlap is real, though:
for a non-toy workload the generated app's substrate may be **regista-backed**
rather than raw SQLite, so the canonical boot AC must be **stack-general** (see
Design step 2): it asserts "the declared shared-state layer initializes,"
whether that layer is a SQLite schema or a regista instance.

## Design — the boot-AC invariant

1. **Explicit signal.** Add `is_substrate: bool` to the decomposer module output
   schema. Detect substrate by this flag; fall back to `ac_ids == []` only for
   back-compat. (Implicit empty-`ac_ids` detection alone was the GR-050 footgun.)
2. **System-owned canonical boot AC.** When a module is substrate, the pipeline
   deterministically assigns `AC-BOOT-01` and injects a fixed AC section into its
   spec **before** `spec_lint`:

   > `## AC-BOOT-01: Walking-skeleton boot`
   > Given a fresh environment, the assembled app starts, initializes its
   > declared shared-state layer (DB schema / regista instance / …), and
   > `GET /healthz` (or `/docs`) returns 200.

   The text is owned by the system, not the decomposer or the spec model. This
   satisfies `check_ac_section_exists` + `check_ac_count_within_band` and gives
   dependency resolution a real AC id to reference.
3. **Discharge = the RFC-038 boot probe, not jury/inspection.** AC-BOOT-01 is
   verified at the conformance gate's boot probe (RFC-038 §2: "does the service
   start and accept a request at all — this alone kills the no-HTTP-server
   case"), with the gate as conformance authority and the jury demoted
   (RFC-038 §3). The per-module test stage does **not** fabricate a meaningful
   AC test for it. This is the anti-vacuity guarantee: the boot AC cannot pass
   by inspection.
4. **Degenerate case (Option 3).** Emit a standalone substrate module (carrying
   AC-BOOT-01) only when **≥2 modules depend on it**. With exactly one
   dependent, inline it — no separate work item; the dependent's real ACs cover
   it.
5. **Reconcile the decomposer-prompt contradiction.** `decomposer.md` currently
   says both "the skeleton is **not a separate module**" (walking-skeleton
   section) and "put shared substrate in **ONE module**" (shared-substrate
   ownership rule). Resolve: a shared substrate with ≥2 dependents *is* a
   separate module and **MUST** set `is_substrate: true` (→ receives
   AC-BOOT-01); a single-dependent substrate is inlined. Remove the standalone
   empty-`ac_ids` allowance.

## Implementation steps

- **`src/factory/prompts/decomposer.md`** — add `is_substrate` to the output
  schema; reconcile the walking-skeleton-vs-ownership-rule contradiction; state
  the ≥2-dependents-as-module / single-dependent-inline rule; stop permitting
  bare empty `ac_ids`.
- **`src/factory/decomposer_model.py` / `decomposer.py`** — parse/carry
  `is_substrate` (fallback: empty `ac_ids`); keep the module_name-keyed cycle/dep
  resolution from the GR-050 fix and ensure substrate self-references stay
  excluded; reject a module flagged `is_substrate` that has feature ACs or `<2`
  dependents (false-positive guard).
- **`populate_work_items.py`** — for a substrate module, set
  `ac_ids = ["AC-BOOT-01"]` (system-owned) instead of the `or ["AC-01"]` default.
- **Spec stage / `spec_lint` call site** — inject the canonical AC-BOOT-01
  section into the substrate spec before `spec_lint`; assert its presence
  post-injection.
- **RFC-038 gate binding** — map AC-BOOT-01 to the boot-probe acceptance check so
  a substrate's conformance *is* the boot-probe result. If the RFC-038 boot probe
  isn't yet landed, provisionally discharge AC-BOOT-01 via the existing
  `outcome_e2e` boot check and record the hard dependency.
- **Tests** — substrate module → AC-BOOT-01 injected, `spec_lint` passes;
  single-dependent substrate → inlined (no separate work item); `is_substrate`
  false-positive (has feature ACs or 1 dependent) → rejected; AC-BOOT-01 →
  boot-probe binding.

## Anti-vacuity guard + watch-metrics (grade GR-051 against these)

- **Hard rule:** AC-BOOT-01 may *never* be marked satisfied by a model/jury
  verdict — only by an executed boot probe.
- **Primary watch-metric:** does any substrate's AC-BOOT-01 go green while the
  boot probe was skipped, stubbed, or host-fallback-without-assertion? If yes,
  the invariant has degenerated into Option 2 — stop and fix.
- **Secondary (RFC-039 carryover):** per-slice mean attempts and failure
  legibility vs the atomic baseline (1.62 on GR-048; `attempt_threshold` 3,
  target ≤2.0). A broken shell must fail **at the substrate's boot AC**, not
  confusingly inside a dependent slice.

## Validation plan (GR-051)

1. Implement the above scoped to url-shortener (substrate AC handling is the only
   changed variable).
2. Re-run the GR-050 DAG through the **same** RFC-038 gate.
3. **Success** = the full DAG locks (no `cannot_proceed` on the substrate), the
   assembled app boots and passes the boot probe, and per-slice failure
   legibility is no worse than the atomic baseline.
4. **Falsification** = the substrate locks but the assembled app still fails to
   boot (AC-BOOT-01 passed without real discharge), or lock rate doesn't improve
   past GR-050's 80%. Either falsifies the system-attached-AC approach → fall
   back to Option 3 (inline *all* substrate, accept the god-agent/topology cost).

## How this could be wrong

- **Boot ≠ schema-correctness.** The boot AC can pass while slices diverge on the
  substrate's *contents* (schema drift). Mitigation: slices' own ACs exercise the
  schema via real persistence; watch for a GR-048 recurrence (one slice real
  sqlite, another fabricating).
- **Mis-flagged `is_substrate`.** A feature module wrongly flagged would skip
  real ACs. Guard (above): `is_substrate` requires zero feature ACs AND ≥2
  dependents, else reject in decomposer validation.
- **Archetype leakage.** CLI/library workloads have no substrate (unit ≈
  deliverable, RFC-039 §31). The `is_substrate` path must be inert for
  non-web-service archetypes; AC-BOOT-01 must not appear in CLI decompositions.

## Scope boundary

Web-service archetype only. Do not generalize the invariant until a second
web-service workload (beyond url-shortener) confirms it, per RFC-039's
change-one-variable discipline.
