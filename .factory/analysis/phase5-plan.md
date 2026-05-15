# Phase 5 Plan — Integration and Outcome Verification

**Date:** 2026-05-14
**Phase:** 5 (current, per spec §10)
**Entry artifact:** GR-027 (Phase 4 exit)
**Directive:** Opus — treat BC-145 as Phase 5 work, shape alongside pipeline-flow changes

---

## Objective

Implement Stage 8 (integration) and Stage 9 (outcome verification) per spec §4. Build the pipeline stages that assemble individual work-item implementations into a runnable software artifact and verify it end-to-end against acceptance criteria.

## Scope

### In scope

1. `integrator` role and `integration` work item type
2. `outcome_verifier` role and outcome-verification work items
3. Integration mechanical gates: cross-module import, assembled-tree mypy, cross-cutting pytest
4. BC-145 design: review/jury verdict upstream routing (structured feedback to implementer/interface_architect)
5. Workflow YAML v5 (`phase5.yaml`) extending `phase4.yaml` with integration + outcome verification stages
6. Synthetic fixture validation on cert-watch full DAG before first real workload

### Out of scope (deferred)

- First real LoB workload (requires RFC-017, RFC-019, RFC-020, RFC-021)
- RFC-022 (initiative primitive)
- Production deployment / artifact bundling for principal (RFC-019)

## Design decisions to make

### 1. Integration work item shape

An `integration` work item links multiple locked `implementation` work items. Questions:
- **Link type:** `derived_from` multiple implementations? Or a new `integrates` link type?
- **Granularity:** one integration per feature group, or per entire DAG?
- **Custom fields:** `assembled_module_paths` (list), `entry_point` (str), `integration_test_path` (str)
- **Scheduler trigger:** jury lock on last implementation in a dependency group → integration creation

### 2. Integrator role prompt

The integrator:
- Reads all locked implementation `.py` files
- Produces an assembled module tree (potentially with `__init__.py` files)
- Must NOT modify implementation signatures (same contract as implementer)
- May add wiring / orchestration code at the module level

### 3. Outcome verifier role prompt

The outcome_verifier:
- Reads the assembled integration artifacts
- Runs end-to-end tests against the AC from the original spec
- Produces a verdict: `pass`, `fail` (with diagnostic), or `cannot_proceed`
- The verdict is terminal for the pipeline; `cannot_proceed` surfaces to principal

### 4. BC-145: Review verdict routing

Current flow (Phase 4):
```
cross_family_review fail → router → new (retry review) → threshold → cannot_proceed
```

Target flow (Phase 5):
```
cross_family_review fail with "upstream_defect" diagnostic
  → router → structured_feedback → implementer / test_author / interface_architect revision
  → jury re-evaluation after revision
```

**Note:** Spec §4 already defines the routing target hierarchy: "Stage 6 cross-family review fail → Stage 4 (implementation) with critique, OR Stage 3 (test author) if the critique implicates the tests." Use this as the default — implementer is the primary target, test_author is the fallback when findings reference test gaps, interface_architect is only reached on disagreement (Stage 7 jury path). This is *not* a new design decision; BC-145 is about *implementing* the spec's existing routing, which Phase 4 left as terminal-on-fail.

**Decisions to make (not open questions):**

- **`DiagnosticKind` taxonomy:** Two kinds suffice — `review_malformed` (reviewer output invalid / refused / JSON-broken) routes to review-retry; `review_found_defect` routes upstream. The reviewer's structured output must declare which. Add a third only with evidence.
- **Findings carrier:** Use a substrate custom field on the *upstream* work item (`review_feedback: list[ReviewFinding]`, append-on-rerun). Not `extra_artifacts` — findings are routing payload, not artifacts. Schema: `{ac_id: str, kind: "impl"|"test", severity: "block"|"advise", body: str, source_review_wi: uuid}`.
- **Routing target selection:** Mechanical, from the finding kind. If any block-severity finding has `kind == "test"`, route to test_author; else to implementer. Mixed test+impl findings produce two new attempts (test_author first, then implementer on the rebuilt tests). No model-mediated routing in Phase 5.
- **Attempt budget:** A review-routed revision counts against the upstream work item's normal `attempt_threshold`. The review work item is not re-attempted until the upstream artifact changes. This prevents budget double-counting.
- **Invalidation via supersession (not state mutation):** Substrate's event store is append-only and `locked` is terminal — there is no "stale" state primitive, and there shouldn't be. When a downstream revision lands and an upstream integration needs redo, **create a new `integration` work item** with refreshed `derived_from` links and a `supersedes` link to the old one. The old integration stays in its terminal state as honest history. Scheduler convention: when resolving "the current integration for feature group X," walk the supersedes chain to the head. Substrate doesn't need to know about supersedes semantics — it's a factory-level convention over a generic link type. No substrate work required.

### 5. Mechanical gate budget

Phase 5 mechanical-gate budget: 18 (per spec §10). Currently at 15. Integration mechanical gates to add:
- `integration_import` — cross-module import check
- `integration_mypy` — type check on assembled tree
- `integration_pytest` — cross-cutting tests

Total mechanical: 15 + 3 = **18, on budget.**

`outcome_e2e` is a model-based verification gate (per spec §4 Stage 9 "runs the assembled software end-to-end against AC"), not a mechanical gate. It joins `cross_family_review` and `jury_quorum`/`jury_disagree` in the LLM-gate category, which is not counted against the mechanical budget. This needs a one-line clarification in spec §10 to make explicit, but is not a budget breach.

### 6. Integration granularity

Decision: **one integration work item per feature group** (where "feature group" = the set of work items linked to a single FR or coherent multi-FR cluster). Rationale:

- Per-DAG integration delays the first integration-gate failure signal until the entire DAG locks. Too coarse to be useful.
- Per-implementation is redundant with inner-gate pytest. Too fine.
- cert-watch has 8 work items spanning FR-01–FR-05 + 3 shared modules (certificate_model, cert_chain_library, database_layer). Natural grouping: one integration per FR (5 integrations), or per module-cluster (3 integrations). Pilot with per-FR; revisit if integration gates over-trigger on the shared modules.

Diamond-dependency note: when multiple FR integrations depend on the same shared module (`certificate_model`), the shared module must be locked before any dependent FR integration is created. Scheduler trigger: integration created when all its `derived_from` implementations are locked *and* all transitively-imported modules are locked.

**Substrate link semantics:** `derived_from` is just a typed link with no cardinality constraint; n-to-1 linking (one integration → N implementations) works natively. Phase 5 workflow YAML adds two declarations: `derived_from: integration → implementation` (n-to-1) and `supersedes: integration → integration` (for §4 invalidation pattern). Nothing else in substrate needs to change.

### 7. Outcome-verification failure routing

If `outcome_e2e` fails, the spec sends it to Stage 10 (principal review). For Phase 5 validation against synthetic fixtures (no principal), define an intermediate path: outcome failure with `routing_hint: <wi_id>` re-opens that upstream work item once (single revision attempt) before terminating. This avoids paging the principal for what a single re-implement might fix, and gives Phase 5 a measurable end-to-end recovery rate without requiring human intervention in the loop.

Decision rule for `routing_hint`: outcome_verifier's structured output must point to a specific `interface_spec`, `implementation`, or `integration` work item when its verdict is `fail`. No hint → terminate to principal.

## Exit criteria (Phase 5)

| Layer | Metric | Target | Rationale |
|---|---|---|---|
| Integration success | Integration lock rate | ≥85% | Assembled tree passes mechanical gates |
| Outcome verification | E2E pass rate (first attempt + 1 routed revision) | ≥70% | End-to-end AC verification succeeds; per §7 routing |
| Cross-module correctness | Zero ImportError in integration | 100% | All cross-module imports resolve |
| Review routing | Review-found defects that produce an upstream revision (not cannot_proceed) | ≥80% | BC-145 effectiveness; substantive over loose ≥50% |
| Review routing correctness | Upstream revision passes review on next attempt | ≥50% | Distinguishes "feedback is actionable" from "feedback is noise" |
| Gate budget | Total mechanical gates | ≤18 | Per spec §10 |
| Capability probe | `outcome_verifier` role validated on probe before pipeline use | required | Per BC-137 framework; no pipeline use of unprobed model roles |

## Execution order

1. **Implement BC-145 routing** — `DiagnosticKind` taxonomy split (`review_malformed` vs `review_found_defect`), `ReviewFinding` schema on upstream work-item custom field, mechanical routing-target selection from finding kind. Tests for both retry and upstream-routing paths. **Land this first** — it's the smallest, most-isolated change and unblocks the Phase 4 cleanup, and Stage 8/9 will benefit from the same routing pattern.
2. **Capability probe `outcome_verifier`** — run BC-137 probe on candidate Tier-A models for the new role. Decide which channel before writing the role prompt; the prompt shape depends on the model's instruction-following profile.
3. **Implement `integration` work item type** — scheduler trigger (shared-module-locked precondition per §6), workflow YAML v5 with two new link-type declarations (`derived_from: integration → implementation` and `supersedes: integration → integration`), role prompt template. Substrate supports both natively; no substrate-side changes.
4. **Implement integration mechanical gates** — `integration_import`, `integration_mypy`, `integration_pytest` in `gate.py`. Reuse Phase 2 patterns from per-WI gates over the assembled tree.
5. **Implement `outcome_verifier` role** — role prompt, work item type, scheduler trigger on integration lock, structured-output schema with `routing_hint` per §7.
6. **Validate on synthetic fixture — GR-028.** cert-watch full DAG with integration enabled, per-FR granularity (5 integrations), dual-family jury preserved from GR-027, BC-145 routing live. Config file: `golden-run-028-config.yaml`. Wall clock budget: ≤120 min (more stages = more model calls).
7. **Iterate** — fix integration gate failures, tune integrator prompt, harden outcome_verifier routing_hint accuracy.
8. **First real workload** — after RFC dependencies (RFC-017, RFC-019, RFC-020, RFC-021) resolved.

**Sequence rationale:** BC-145 is the lowest-risk step (no new stages, only new routing on existing failure path) and provides the routing infrastructure outcome_verifier reuses in step 5. Landing it first surfaces routing-logic bugs against the familiar Phase 4 surface area before stacking Stage 8/9 on top.

## Risks

1. ~~**Integration gate over budget**~~ — resolved: outcome_e2e is an LLM gate, not mechanical (see §5). Spec §10 needs one-line clarification.
2. **Cross-module import complexity** — cert-watch has diamond dependencies on shared modules. Mitigation: scheduler precondition that shared modules are locked before any dependent integration is created (§6).
3. **BC-145 interacts with integration invalidation** — a module revision after integration requires re-integration. Decision in §4: create a new integration work item with a `supersedes` link to the old one. Substrate supports this natively (no substrate work; append-only event store + typed links). Scheduler must traverse the supersedes chain when resolving "current" integration.
4. **Outcome verifier is a new model role** — capability probe is step 2 in execution order; no pipeline use before probe passes.
5. **BC-146 regression risk** — the assertion-counter fix changes gate output for test files using `pytest.raises`. The 16ee8dac escalation in GR-027 would no longer occur. Confirm in GR-028 that the same fixture passes the test_suite_assertions gate cleanly.
6. **Routing-hint accuracy** — outcome_verifier's `routing_hint` may target the wrong upstream work item. Fallback: if the hinted WI passes its existing gates unchanged after the routed revision attempt, treat the outcome failure as terminal (don't burn another round). Need telemetry on routing-hint hit rate.

## Dependencies

- Substrate: no known blockers; current API supports work items, links, custom fields.
- RFC-017: operational survivability — nice to have, not blocking skeleton.
- RFC-019: artifact bundling — required before principal delivery, not before validation.
- RFC-020: project archetype catalog — helps cold-start, not blocking.
- RFC-021: spec mutation — needed for real workload, not for synthetic validation.
