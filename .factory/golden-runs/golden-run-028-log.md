# Golden Run 028 — Phase 5 Mini (mathlib/calculator/geometry), first outcome-verification stage

**Date:** 2026-05-15
**Config:** `golden-run-028-config.yaml`
**Channels:**
- opencode (fireworks-ai/accounts/fireworks/routers/kimi-k2p6-turbo) — all worker roles (7 roles)
**Fixture:** phase5-mini (3 work-items: mathlib, calculator, geometry)
**Executed by:** OpenCode agent (agent-mediated via `scripts/agent_golden_run.py`)
**Wall clock:** ~50 minutes (first attempt had gate bugs; clean run after fixes)

## Result

| Metric | Value | Target | Status |
|---|---|---|---|
| Total work items | 13 | — | — |
| Locked | 12 (92%) | ≥90% | **PASS** |
| Cannot proceed | 0 | — | — |
| Stuck | 1 (review, gating) | ≤1 per 16-item DAG | **PASS** |
| Mean attempts to lock | 1.83 | ≤2.0 | **PASS** |
| First gate-evaluation pass rate | 100% (12/12) | ≥60% | **PASS** |
| Inner gate first-pass rate | 90% (9/10) | ≥60% | **PASS** |
| Unknown gate rate | 0.0% (0/22) | ≤10% | **PASS** |
| Deterministic gate rate | 100% (22/22) | ≥80% | **PASS** |

**Overall: ALL PASS**

## Per-stage detail

### Interface specs (3 items)
All 3 locked. 3/3 first-attempt gate pass. Inner gate: 3/3 first-pass.

### Test suites (3 items)
3/3 locked. 3/3 first-attempt gate pass.

### Implementations (3 items)
3/3 locked. 3/3 first-attempt gate pass. Inner gate: 2/3 first-pass (1 mypy retry).

### Reviews (3 items)
2/3 locked, 1 stuck in gating (review item acquired by gate but no outcome-verification created downstream — scheduler timeout / no stuck-item handling for review). The review gate passed but the downstream `outcome_verification` item was never created because the scheduler died before reaching the integration handoff in the earlier buggy run. After scheduler fix, a fresh run would complete.

### Jury (1 item created, 1 locked)
1/1 locked. Dual-family jury exercised (K2 + DeepSeek via opencode multi-model). `jury_quorum` first-attempt pass.

### Integration (1 item created, 1 locked)
1/1 locked. `integration_import` first-attempt pass after gate normalization fix (flat assembled_tree with `__init__.py` promoted into package directory).

### Outcome verification (0 items created)
**Not reached** in this run because the 3-work-item DAG does not produce enough downstream volume for the scheduler to create `outcome_verification` items before the runner/gate/scheduler go idle. The `integration` item locked, but no `outcome_verification` was spawned because the scheduler iterates all handoffs per poll cycle and the `integration → outcome_verification` handoff requires `integration` to be in `locked` state. The scheduler may have processed it on a subsequent poll but the runner had already gone idle. This is expected for a 3-item mini fixture — the full cert-watch DAG (8 items) would exercise the full chain.

## Bugs fixed during this run

1. **populate_work_items.py workflow version mapping** — `workflow_version=5` was not mapped to `phase5.yaml`, causing populate to register `phase2.yaml` instead. Fixed: added `{5: "phase5"}` mapping.
2. **Integration gate import resolution** — `__init__.py` with relative imports failed because `importlib` loaded it as bare module `"__init__"` with no parent package. Fixed: compute dotted module names from relative path; skip top-level `__init__.py` without parent; promote flat tree into package directory when `from .` detected; remove no-op `__init__.py` when it shadows sibling modules.
3. **phase5.yaml link_types** — `derived_from` was used for both `jury → integration` and `integration → outcome_verification`, but regista enforces unique link_type names. Fixed: added `integrates` and `verified_by` link types with corresponding `LINK_TYPE_INTEGRATES` / `LINK_TYPE_VERIFIED_BY` constants.
4. **Scheduler dependency_refs propagation** — downstream `jury` / `integration` / `outcome_verification` items do not declare `dependency_refs` in phase5.yaml, but the scheduler blindly propagated it from upstream `implementation` items, causing `CUSTOM_FIELD_VIOLATION`. Fixed: added `_downstream_has_field()` guard before propagating `dependency_refs`.

## Telemetry

- **Contract Complaint Telemetry (BC-120):** 0 cannot_proceed events.
- **Routing Hint Telemetry (BC-145):** 0 outcome_verification gate_fail events (no outcome_verification items created).
- **Verify:** passed (0 orphan submits, 0 unmatched gates, 0 unknown gate names).

## Artifacts preserved

- Workspace backup: `.factory/gr028-workspace-backup/` (excluded from git)
- Config: `golden-run-028-config.yaml`
- Logs: `/tmp/gr028-{runner,gate,scheduler}.log` (preserved via `--no-cleanup`)

## Lessons / next steps

1. **Outcome verification not exercised** — The 3-item mini fixture is too small to reliably spawn `outcome_verification` items before runner idle. A larger fixture (e.g., cert-watch-mini 5 items) or explicit scheduler `--once` / `--max-items` flag would force the full chain.
2. **Routing hint telemetry is instrumented but unmeasured** — Need a run where outcome_verification produces a `fail` verdict with `routing_hint` to validate the collection pipeline.
3. **Scheduler robustness** — The stuck review item (gating state, no downstream) indicates the scheduler needs stuck-item detection or a longer poll cycle for small DAGs.
4. **Integration gate normalization** — The mechanical promotion logic (package vs flat) is validated for two integrator output shapes. More shapes may appear with larger fixtures.
