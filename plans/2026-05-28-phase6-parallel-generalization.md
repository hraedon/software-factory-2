# Phase 6 (execution amendment) — Parallel Generalization

**Status:** proposed 2026-05-28
**Author:** Opus 4.8 (portfolio review)
**Amends, does not replace:** `2026-05-24-phase6-second-domain-and-decomposer-b.md`
and the locked `rfc023-phaseb-contract.md`.
**Strategic role:** Track 2 of the 3-week grant plan — the independent,
parallel-friendly track. Golden runs are embarrassingly parallel; this is where
abundant grant resource has the highest marginal return in the portfolio.

## What changes from the 2026-05-24 plan

The original Phase 6 plan is correct and its Phase B contract is already locked.
Two amendments, both driven by the grant's resource profile:

### Amendment 1 — Lock Candidate 2 as a *required* workload, not a recommendation

The original W1 offered three candidate second-domain workloads and recommended
Candidate 2 (the regista event-log dep-graph viewer) tentatively. **Make it
required.** Reason it was undersold: Candidate 2 is the only choice that solves
two portfolio problems at once — it gives sf2 a second domain *and* it makes sf2
the first real external consumer of regista's API, which is exactly the
consumer-forcing pressure regista needs (regista is over-built relative to
demonstrated use). Candidates 1 and 3 give a second domain but contribute
nothing back to the constellation.

### Amendment 2 — Run 3–4 workloads in parallel, not one sequential second domain

The original plan runs one second-domain workload (GR-040 baseline, GR-041
Phase B). With grant resource, the overfit risk (one datapoint) is best killed
by N datapoints at once. Author 3–4 cert-watch-scale workloads of *different
module shapes* and run them concurrently:

1. **regista dep-graph viewer** (Candidate 2 — required; read-only, single
   binary output, dogfoods regista).
2. **log-redaction CLI** (Candidate 1 — file IO + structured config +
   side-effecting audit log).
3. **breadcrumb-velocity reporter** (Candidate 3 — smallest; directory read +
   markdown report).
4. *(optional 4th, principal's pick)* — a web-service-shaped workload if the
   team wants to probe a different archetype early (originally Phase 6.2).

Each is a distinct module shape from cert-watch, so passing all of them is
real evidence of generalization rather than re-fitting to a second shape.

## Work items

- **W1.** Author Level-1+ specs for workloads 1–3 (sidecar `spec.yaml` preferred,
  per the locked contract input schema). Check in under
  `tests/fixtures/<workload-name>/`. *Parallelizable: one agent per spec.*
- **W2.** Implement RFC-023 Phase B decomposer per the locked contract
  (`rfc023-phaseb-contract.md`). Sonnet primary, K2 cross-family review on the
  decomposition document itself. Single implementation; co-designed against all
  workloads, not tuned per workload.
- **W3.** GR-040..N(A): Phase A (deterministic) baseline golden run on each
  workload. *Parallelizable across workloads.*
- **W4.** GR-040..N(B): Phase B (model-driven) golden run on each workload.
  *Parallelizable across workloads.*
- **W5.** Decision gate (the real test): across all workloads, does Phase B
  produce sensible decompositions **without per-workload tuning**? Compare
  module-naming quality, FR-grouping coherence, and lock rates A-vs-B per
  workload. Update AGENTS.md Phase 6 status with the multi-workload result.

## Acceptance

- 3 (or 4) second-domain specs checked in, of distinct module shapes.
- Phase B decomposer implemented to the locked contract; semantic-naming gate
  enforced (no `fr01`-style names, no generic suffixes).
- A and B golden runs executed on every workload.
- W5 written up with a defensible generalize-vs-curve-fit verdict backed by
  per-workload evidence, not a single run.

## Sequencing & dependencies

- **Fully independent of Track 1** (the bundle slice). Run concurrently.
- Candidate 2 dogfoods regista's consumer API — surface any friction as regista
  breadcrumbs; it may produce a small regista follow-on (e.g. a server-side
  `query_events()` filter). That feedback is a *feature* of picking Candidate 2.
- Requires Postgres + model channels (existing golden-run prerequisites).

## What to resist

- Do not keep polishing the pipeline against cert-watch. The ALL-PASS milestone
  (GR-038) is reached; the only evidence that matters now is multi-workload.
- Do not pull in agent-wake or agent-provenance integration — they remain
  composition seams, not dependencies, per the 2026-05-24 plan §5.
