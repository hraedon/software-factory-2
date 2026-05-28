# Phase 6 — Second-domain workload + RFC-023 Phase B forcing function

**Status:** proposed
**Author:** opus-4-7
**Date:** 2026-05-24
**Origin:** AGENTS.md Phase 6 priority #1 (RFC-023 Phase B), Sonnet-4-6 reflection 2026-05-19 ("all 38 golden runs are cert-watch"), Phase-5-exit followup window B (real workload selection).

## Motivation

Phase 5 exited at GR-038 with all-pass; GR-039 confirmed under RFC-011 + BC-195. Bug count just reached zero (Session 49). The remaining gate to "Phase 6 substantively underway" is empirical: **every golden run to date has been cert-watch**. The pipeline is implicitly tuned to one workload's module shape, FR count, and dependency graph. Generalization claims cannot be assessed from one datapoint.

RFC-023 Phase B (model-driven decomposer with semantic module naming and FR grouping) is the listed #1 Phase 6 gate. Building Phase B against cert-watch alone re-fits it to cert-watch. The leverage move is to **co-design Phase B against two workloads from the start**: cert-watch (known) + one second-domain workload sized at cert-watch-scale. Phase B is correct only if it produces a sensible decomposition for both without per-workload tuning.

The `catalog/cli-tool` archetype already exists (RFC-020 landed). A small CLI tool is the natural second-domain candidate; it exercises the archetype, the decomposer, and the integration/outcome stages on shapes the pipeline hasn't seen.

## Scope

- **W1** — Second-domain workload selection and spec authoring.
- **W2** — RFC-023 Phase B implementation (model-driven decomposer), co-designed against both workloads.
- **W3** — GR-040: golden run on the second-domain workload using Phase A decomposer (baseline).
- **W4** — GR-041: golden run on the second-domain workload using Phase B decomposer (proof).
- **W5** — Decision gate: is decomposer Phase B generalising or curve-fitting? Updates to AGENTS.md Phase 6 status.

## Non-scope

- agent-wake integration (consumer of external events). Scaffold-only sibling; revisit when sf2 has a workload that needs mid-run external signal.
- agent-provenance attestation of sf2 pipeline actions. Sibling is skeleton-stage; the integration seam will be designed in a separate plan after agent-provenance ships harness hooks.
- RFC-027 test efficacy mutation gate. Listed Phase 6 #5; needs a second workload's failure modes to design against — pulled in only if W3/W4 surface coverage-gap evidence.
- Third workload, web-service archetype. Earliest Phase 6.2.

## Design

### W1 — Workload selection

**Candidates** (CLI-tool-shaped, 3–6 modules, 8–15 interface specs):

1. **A log-redaction CLI** — reads structured logs, applies redaction rules from YAML, emits redacted stream + audit JSONL. Modules: rules parser, redactor, audit writer, stream IO, CLI entry. Naturally exercises file IO, structured config, and side-effecting outputs (audit log).
2. **A dependency-graph viewer for regista event logs** — reads regista event log, produces a DOT graph of work-item dependencies. Modules: regista reader, graph builder, DOT emitter, CLI. Has the advantage of dogfooding regista.
3. **A breadcrumb-velocity reporter** — reads `breadcrumbs/` directory, computes the 7-day rolling count from RFC-032, emits a markdown report. Smallest of the three.

**Recommendation:** Candidate 2 (regista dep-graph viewer). It (a) dogfoods regista, surfacing real consumer-side API friction; (b) has a tight, definable AC ("DOT output renders the same shape as the regista web UI for the same run"); (c) is the kind of internal tool the principal actually benefits from; (d) is a different module shape from cert-watch (read-only, no scheduled side effects, single-binary output).

Decision is the principal's; this plan lists the options and proceeds once selected.

**Output:** A `Level-1+` spec in either `spec.md` freeform or `spec.yaml` sidecar (Phase 6 prefers sidecar; if socratic-specification can produce one, use it). Checked in under `tests/fixtures/<workload-name>/`.

### W2 — RFC-023 Phase B

**Current state:** Phase A (deterministic) reads `spec.yaml`/`spec.md` and produces one fixture per FR with fr_ids and dependency_hints. Phase B is "model-driven decomposition with semantic module naming and FR grouping."

**Phase B contract** (to be locked in W2 design step before implementation):
- **Input:** Level-1+ spec (`spec.yaml` preferred; `spec.md` as fallback).
- **Output:** A decomposition document with N module fixtures, each with:
  - semantic module name (not `FR-001`);
  - the set of FRs the module owns;
  - interface ACs at the module boundary;
  - dependency edges between modules (not FRs).
- **Constraint:** Phase B output must be feed-compatible with `populate_work_items.py` so the rest of the pipeline is untouched.

**Channel placement:** Decomposer is a heavy-judgment role (RFC-024-class long-context task). Recommended placement: Sonnet primary, K2 cross-family review on the decomposition itself (jury at the decomposer stage, not just at downstream stages). The decomposition is high-leverage; one bad call propagates to every downstream item.

**Co-design discipline:** No Phase B feature lands without producing acceptable decompositions for **both** cert-watch and the W1 workload. If a feature helps one and hurts the other, redesign rather than gate behind a flag.

### W3 — GR-040 (Phase A baseline)

Run the new workload through the existing Phase A decomposer. This produces the comparison baseline. Expected: decomposition is per-FR, module names are FR-shaped, dependency edges are flat. Locks may or may not happen — that's data either way.

### W4 — GR-041 (Phase B proof)

Run the new workload through Phase B. Acceptance is qualitative: does the decomposition look like what a senior engineer would write? Quantitative: lock rate within 10 percentage points of cert-watch's GR-038 baseline (87%); if it's worse, Phase B is curve-fit.

### W5 — Decision gate

A short writeup (`plans/gr040-gr041-analysis.md` or in the worklog) answering:
- Did Phase B produce a sensible decomposition for both workloads without tuning?
- What new defect classes (if any) did the second workload surface?
- Are any RFCs newly unblocked or newly forced (RFC-027 in particular)?
- Phase 6 status: substantively underway, blocked, or done?

## Cross-project hooks

| Sibling | What sf2 needs | What sf2 gives |
|---|---|---|
| **regista** | `query_events()` server-side filter to fix BC-196 properly (currently client-side cache). If W1 picks Candidate 2 (regista dep-graph viewer), the workload doubles as regista consumer-API stress test. | Real-workload consumer feedback; possibly a regista plan-015 item if the dep-graph viewer surfaces friction. |
| **agent-notes** | Continue using breadcrumb/memory MCPs for cross-session state. No new dependency. | Real-workload validation of the breadcrumb MCP under sustained Phase 6 work. |
| **agent-wake** | Nothing this plan. Scaffold-only sibling. | Composition seam: after W5, evaluate whether mid-run external-event injection (e.g., "principal canceled this item") is something sf2 wants. Not a blocker. |
| **agent-provenance** | Nothing this plan. Skeleton-stage sibling. | Composition seam: each sf2 model invocation is a candidate provenance event. The integration design belongs in a separate plan once agent-provenance ships harness hooks. Explicitly deferred. |
| **regista-eventlog MCP** | Use `list_golden_runs` + `golden_run_summary` for GR-040/GR-041 review instead of grepping logs. Already integrated; just keep using. | Validation under Phase 6 cadence. |

## Work-item breakdown

| ID | Item | Implementer tier | Effort |
|---|---|---|---|
| W1.1 | Principal selects workload from 3 candidates | Opus + principal | 1 sync session |
| W1.2 | Author spec.md (or spec.yaml if socratic-spec is ready) for chosen workload | Opus + principal | half session |
| W1.3 | Check spec in under `tests/fixtures/<workload>/`, populate via Phase A | Sonnet | 1 hour |
| W2.1 | Lock Phase B contract (input/output schema, channel placement, co-design discipline) | Opus | half session |
| W2.2 | Implement Phase B decomposer in `populate_work_items.py` (or new `src/factory/decomposer.py`) | Opus + Sonnet | 2 sessions |
| W2.3 | Tests: synthetic decompositions for both workloads, snapshot-style | Sonnet | 1 session |
| W3 | GR-040: run new workload through Phase A; capture as baseline | Sonnet (run) + Opus (analysis) | 2 hours run + 1 hour writeup |
| W4 | GR-041: run new workload through Phase B; compare to GR-040 | Sonnet (run) + Opus (analysis) | 2 hours run + 1 hour writeup |
| W5 | Decision-gate writeup; AGENTS.md update; Phase 6 status | Opus | half session |

Total: ~1.5 weeks of focused work, dominated by W2.2 (Phase B implementation) and the two golden runs.

## Acceptance

- W1: spec checked in; Phase A produces a populated work-item DAG.
- W2: Phase B decomposer ships behind no flag; default for new specs. Both cert-watch and W1 workload produce decompositions whose module names are semantic, not FR-shaped.
- W3: GR-040 completes (lock rate may be anything; the run completing end-to-end is the bar).
- W4: GR-041 completes with lock rate ≥ GR-038 minus 10 pp on the new workload. If worse, W5 writeup explains why and either patches Phase B or files a follow-up plan.
- W5: AGENTS.md updated; Phase 6 status moved from "in progress" to a more specific state ("Phase 6.1 — Generalization validated on N=2 workloads" or similar).

## Risks

| Risk | Mitigation |
|---|---|
| Phase B over-fits to one of the two workloads. | Co-design discipline: no Phase B feature lands without acceptable decompositions for both. |
| W1 workload spec author bias produces a spec shaped like cert-watch. | Pick a workload with a structurally different module pattern (read-only, single-output, no scheduled side effects). Candidate 2 satisfies this. |
| GR-040 catastrophically fails (Phase A can't decompose the new workload at all). | Useful failure: surfaces what Phase B must fix. Don't pre-empt by tuning Phase A. |
| GR-041 lock rate is mediocre on the new workload. | Expected within 10 pp. If worse, W5 explicitly documents Phase B as not-yet-generalised; either iterate or accept and add a third workload. |
| Decomposer model placement (Sonnet primary, K2 review) burns more wall-clock than expected. | Phase B is a one-time-per-workload step. Wall-clock there is well-spent. |
| RFC-027 (test efficacy) becomes a hard blocker mid-W4. | Acceptable. W5 will surface it. RFC-027 is already listed as Phase 6 #5; promotion is fine. |

## Open questions

1. **Phase B's place in the pipeline:** is it run by `populate_work_items.py` as a pre-pass, or is it Stage 0 of the pipeline proper (with its own gate)? RFC-023 leans the latter. Decide in W2.1.
2. **Sidecar `spec.yaml` produced by socratic-specification:** is it ready, or does W1 fall back to `spec.md`? Check socratic-spec status before W1.2.
3. **Acceptance signal for the new workload's outcome verification:** cert-watch has a runnable artifact. Candidate 2 (regista dep-graph viewer) does too. Confirm runnable-AC alignment in W1.2.
4. **One workload or two for Phase 6 exit?** This plan validates N=2 (cert-watch + new). Whether N=2 is enough for Phase 6 exit, or N=3 is required, is the principal's call in W5.

## Notes

- This plan does not file any new RFCs. Phase 6 work is now executing existing RFCs (023, 026, 022 already in place; 027 next when forced).
- This plan deliberately leaves agent-wake and agent-provenance as composition seams, not dependencies. Forcing those integrations now would be premature; both are scaffold/skeleton stage. The right time to design the seams is after W5, when sf2's Phase 6 surface is concrete enough to know what to expose to provenance and what events to consume from wake.
- The cleanest exit from this plan is: Phase 6.1 declared done at N=2, Phase 6.2 plan opens with web-service archetype as the third workload + agent-provenance harness integration as a parallel track.
