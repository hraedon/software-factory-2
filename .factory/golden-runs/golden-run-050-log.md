# GR-050 — Phase C Decomposer + RFC-039 (Deliverable-Driven Decomposition)

**Date:** 2026-05-30
**Config:** golden-run-050-config.yaml
**Fixture:** url-shortener (spec.yaml, decomposed via Phase C model)
**Channels:** opencode (kimi-k2p6-turbo), claude-code (sonnet), opencode (mimo-v2.5-pro)
**Executor:** GLM-5.1 agent
**Wall clock:** ~7 min (01:32:02–01:39:25 active; 01:42 telemetry)
**Workflow version:** 5 (full pipeline)

## Purpose

Test RFC-039 (deliverable-driven decomposition + walking skeleton) through the pipeline. This is the first run where the decomposer produces Phase C modules (deliverable-altitude, each owning HTTP endpoint + DB queries + Pydantic models) instead of Phase A atomic FR-based modules. Validates:
1. The Phase C decomposer prompt is followed by the model
2. The decomposer validation gates accept shared-fr_id modules (cycle detection fix)
3. The dependency resolution correctly maps multi-module FR-IDs to the right substrate
4. The pipeline can process deliverable-altitude work items through all stages

## Bugs fixed during this run

### 1. Cycle detection false positive (decomposer_model.py)

**Root cause:** Phase C allows multiple modules to share the same `fr_id` (e.g., `link_store` substrate and `link_creator` endpoint both claim FR-01). The cycle detection graph used `fr_id` as node identifier. When `link_creator` depends on FR-01, the code saw FR-01→FR-01 (self-cycle) because the dict was keyed by fr_id and the last module's deps overwrote the first's.

**Fix:** Rewrote cycle detection to operate on `module_name` (unique) instead of `fr_id`. Build a `fr_to_modules_map` that maps each fr_id to all modules claiming it. When a module lists its own fr_id as a dependency, it means "depends on OTHER modules with that fr_id" (the substrate), so self-references are excluded.

### 2. Dependency resolution maps to wrong module (decomposer_model.py)

**Root cause:** `fr_to_module` dict was `{fr_id: module_name}` — when multiple modules share an fr_id, only the last one survived. `link_creator`'s `dependency_fr_ids: ["FR-01"]` resolved to itself instead of the `link_store` substrate.

**Fix:** Changed to `fr_to_modules_map: dict[str, list[str]]` and resolved each module's dependencies to all modules with that fr_id, excluding self.

## Result summary

| Metric | Value | Target | Pass? |
|---|---|---|---|
| Total work items | 5 | — | — |
| Locked (interface_spec) | 4 (80%) | — | — |
| Cannot proceed | 1 (link_store) | — | — |
| Test suites created | 0 | — | — |
| Implementations | 0 | — | — |
| Pipeline progress | interface_spec only | full DAG | FAIL |
| Mean attempts | 2.0 | ≤2.0 | PASS |
| First gate-eval pass rate | 100% (4/4) | ≥60% | PASS |
| Inner gate first-pass rate | 100% (4/4) | ≥60% | PASS |
| Unknown gate rate | 0% | <1% | PASS |
| Deterministic gate rate | 100% (8/8) | ≥80% | PASS |
| Telemetry verify | True | True | PASS |

## Phase C decomposition output

Model: MiMo-V2.5-Pro (opencode channel). The model followed the Phase C prompt correctly:

| Module | FR-ID | ACs | Dependencies |
|---|---|---|---|
| link_store | FR-01 | (none) | None |
| link_creator | FR-01 | AC-01, AC-02, AC-07, AC-08 | link_store |
| link_resolver | FR-02 | AC-03, AC-04, AC-10 | link_store, link_creator |
| stats_reader | FR-03 | AC-05 | link_store, link_resolver |
| link_lister | FR-04 | AC-06, AC-09 | link_store, link_creator |

The decomposition rationale (from the model): "Decomposition follows vertical feature slices: one module per HTTP endpoint, each owning its router, Pydantic models, DB queries, and error formatting. link_store is the shared substrate (schema + app factory) that every slice imports. FR-05 (validation) is absorbed into link_creator."

## Per-stage detail

### Decomposition (Phase C)

- Attempt 0: Model produced valid Phase C output on first try (after cycle detection + dependency resolution fixes)
- All validation gates passed (module_small warnings for link_store and stats_reader are soft)
- Decomposer fallback NOT triggered (no Phase A fallback needed)

### Interface architect (5 items)

- **link_store** (0aa5fd80): Claimed, model invoked, went to `cannot_proceed`. Diagnostics: "The spec excerpt for db_substrate contains no AC prose; it only describes 'SQLite schema and database connection for links and hits tables with WAL mode'." The module has no acceptance criteria, so the pipeline cannot validate its output.
- **link_lister** (24d36126): Claimed → inner_pytest passed (retry=0) → submitted → gate_pass. Locked.
- **link_creator** (28709f16): Claimed → inner_pytest passed (retry=0) → submitted → gate_pass. Locked.
- **stats_reader** (4c2111de): Claimed → inner_pytest passed (retry=0) → submitted → gate_pass. Locked.
- **link_resolver** (c8abb009): Claimed → inner_pytest passed (retry=0) → submitted → gate_pass. Locked.

### Scheduler

- Created 0 downstream items. The scheduler's `_all_dep_specs_locked` check requires ALL dependency_refs to point to locked items. Since link_store is `cannot_proceed`, no test_suite items can be created for any module.

## Failure analysis

### link_store → cannot_proceed (root cause: no ACs)

The Phase C decomposer correctly identified `link_store` as the shared substrate (SQLite schema, app factory) with NO acceptance criteria. The pipeline requires every work item to have at least one AC to validate its output. Without ACs:
- The runner invoked the model, which produced a spec describing the substrate
- The spec had no ACs → spec_lint flagged it → `cannot_proceed`
- Even if the spec had been accepted, there would be no test cases to validate

**This is a design-level issue, not a bug.** The Phase C decomposer prompt explicitly allows modules with empty `ac_ids` for substrate/shared-infrastructure modules. But the pipeline has no mechanism to handle such modules. Options:
1. **Assign a walking skeleton AC** to the substrate (e.g., "Given a fresh database, the app starts and responds to GET /docs with 200")
2. **Treat substrate modules as a special type** that bypasses the AC-gated validation
3. **Merge the substrate into the first dependent module** (no separate substrate work item)

### Pipeline stuck at test_suite stage

All 4 locked interface_specs depend on link_store (`cannot_proceed`). The scheduler won't create test_suite items for them because `_all_dep_specs_locked` returns False. This is the correct behavior — the pipeline correctly detects that a dependency is broken.

## Model-family performance

| Model | Channel | Role | Items | 1st-Attempt Pass |
|---|---|---|---|---|
| kimi-k2p6-turbo | opencode | interface_architect | 4 | 100% |
| mimo-v2.5-pro | opencode | decomposer | 1 | 100% |

(Only interface_architect stage was reached.)

## Telemetry integrity

- unknown_gate_name_count: 0
- orphan_submit_count: 0
- unmatched_gate_count: 0
- confounding_warning_count: 0
- verify_passed: True

## Artifacts preserved

- Workspace: `/tmp/sf2-golden-050/` (preserved, --no-cleanup)
- Logs: `.factory/logs/gr050/`
- Decomposer output: `/tmp/sf2-golden-050/.decomposed/`

## Lessons and next steps

1. **Phase C decomposition works — the model follows the prompt.** MiMo-V2.5-Pro produced deliverable-altitude modules with correct altitude-alignment rules (HTTP endpoints, DB queries, Pydantic models all owned by the same module). This is the first validated Phase C decomposition.

2. **Substrate modules need ACs.** The biggest design gap exposed by this run: a substrate module with `ac_ids: []` is a dead end. The pipeline needs either (a) a walking skeleton AC assigned to substrates, or (b) a bypass mechanism for infrastructure-only modules. This is the immediate blocker for GR-051.

3. **Cycle detection and dependency resolution are fixed.** Two bugs found and fixed in decomposer_model.py. The model's Phase C output was correct all along — the validation code was wrong.

4. **The pipeline stalled at 80% lock rate because of a single-point-of-failure substrate.** In Phase A (atomic decomposition), every module has at least one AC, so this never happens. In Phase C, the substrate is a new architectural element that the pipeline doesn't know how to handle.

5. **Next concrete step: GR-051.** Either (a) add a minimal "app starts" AC to the substrate in the decomposer prompt, or (b) have the populate step skip AC-less work items and treat their output as always-available infrastructure. Then re-run the full DAG.
