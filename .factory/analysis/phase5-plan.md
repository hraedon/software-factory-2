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
  → router → structured_feedback → implementer/interface_architect revision
  → jury re-evaluation after revision
```

Key design:
- `DiagnosticKind` taxonomy: `review_malformed` (review-retry) vs `review_found_defect` (route upstream)
- Upstream routing target: implementer if defect is in code; interface_architect if defect is in contract
- How to carry review findings into the next implementer attempt: `custom_fields.review_feedback` or `extra_artifacts`?
- Invalidation: if a module is revised after integration, the integration item must be re-evaluated or recreated

### 5. Mechanical gate budget

Phase 5 budget: 18 gates (per spec §10). Currently at 15. Integration gates to add:
- `integration_import` — cross-module import check
- `integration_mypy` — type check on assembled tree
- `integration_pytest` — cross-cutting tests
- `outcome_e2e` — end-to-end AC verification (may be model-based, counts as one gate)

Total: 15 + 4 = 19. **Over budget by 1.** Decision needed: either (a) one existing gate has not fired in 3 GRs and can be removed, or (b) spec amendment with rationale required per §10.

## Exit criteria (Phase 5)

| Layer | Metric | Target | Rationale |
|---|---|---|---|
| Integration success | Integration lock rate | ≥85% | Assembled tree passes mechanical gates |
| Outcome verification | E2E pass rate | ≥70% | End-to-end AC verification succeeds |
| Cross-module correctness | Zero ImportError in integration | 100% | All cross-module imports resolve |
| Review routing | Review defects routed upstream | ≥50% of review-found defects | BC-145 effectiveness |
| Gate budget | Total mechanical gates | ≤18 | Per spec §10 |

## Execution order

1. **Design BC-145 routing shape** — write RFC-lite in `.factory/analysis/phase5-bc145-design.md`
2. **Implement `integration` work item type** — scheduler, workflow YAML, role prompt template
3. **Implement integration mechanical gates** — gate.py additions for cross-module checks
4. **Implement `outcome_verifier` role** — role prompt, work item type, scheduler trigger
5. **Validate on synthetic fixture** — cert-watch full DAG, manual run (GR-028)
6. **Iterate** — fix integration gate failures, tune integrator prompt
7. **First real workload** — after RFC dependencies resolved

## Risks

1. **Integration gate over budget** — may need to remove a gate or amend spec.
2. **Cross-module import complexity** — cert-watch has diamond dependencies; integration must handle them.
3. **BC-145 interacts with integration invalidation** — a module revision after integration requires re-integration. Substrate link model may not support "invalidate downstream" natively.
4. **Outcome verifier is a new model role** — needs capability probe before pipeline use (BC-137 framework).

## Dependencies

- Substrate: no known blockers; current API supports work items, links, custom fields.
- RFC-017: operational survivability — nice to have, not blocking skeleton.
- RFC-019: artifact bundling — required before principal delivery, not before validation.
- RFC-020: project archetype catalog — helps cold-start, not blocking.
- RFC-021: spec mutation — needed for real workload, not for synthetic validation.
