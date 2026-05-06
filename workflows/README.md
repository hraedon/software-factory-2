# Software Factory v2 — Substrate Workflow Definitions

Design-time workflow YAMLs for the software factory pipeline. These exercise substrate's workflow schema against the pipeline shape described in `spec.md` §4.

## State machine

Both Phase 1 and the full pipeline use the same 4-state lifecycle:

```
new ──claim──▶ in_progress ──submit──▶ gating ──gate_pass──▶ locked
  ▲                                        │                 (terminal)
  └──────────────gate_fail─────────────────┘
```

Every work-item progresses linearly: `new → in_progress → gating → locked`. On gate failure, the item returns to `new` for re-claim. The `attempt_threshold` (3) triggers substrate's escalation mechanism — after 3 claim attempts, `needs_review=true` and an `escalated` event fires. The runner monitors this flag and surfaces to the principal.

### Why this shape

1. **Revision creates new work-items, not state cycles.** When the jury disagrees on an implementation, the runner creates a new `interface_spec` work-item (linked to the original via `revision_of`) rather than cycling the locked interface back to `new`. This preserves the audit trail and keeps the state machine acyclic.

2. **Routing is a runner concern, not a substrate concern.** The failure routing table in spec §4 (Stage 5 fail → Stage 4, Stage 7 disagreement → Stage 2) operates on *different* work-items. Substrate records the transitions; the runner reads the events and creates/claims the appropriate downstream work-item. The state machine doesn't need per-stage states.

3. **`gating` is the handoff point.** The `submit` transition moves the item from agent control to gate control. The runner's gate code (type check, schema validation, lint) runs while the item is in `gating`. The gate code then calls `gate_pass` or `gate_fail`. This separation ensures the gate result is a substrate event for auditability.

4. **Claims and attempts track retries.** Each `claim` acquires a substrate claim with an incremented `attempt_number`. After `attempt_threshold` failed claims, the escalation mechanism fires. The runner doesn't need to track retries — substrate does it.

## Phasing

| File | Version | Phase | Scope |
|------|---------|-------|-------|
| `phase1.yaml` | 1 | Phase 1 | `interface_architect` role, `interface_spec` type only |
| `full_pipeline.yaml` | 2 | Phase 2+ | All roles, all types, all links |

Phase 1 validates the single-role end-to-end loop. The runner uses `phase1.yaml` to register the workflow and exercises the `interface_architect → mechanical_gate → locked` path. Once >90% first-attempt pass rate is achieved, Phase 2 switches to `full_pipeline.yaml` and adds roles one at a time.

The two YAMLs are separate substrate workflow versions (`version: 1` and `version: 2`). Existing work-items created under version 1 continue to operate on their pinned version (BR-02). New work-items created under version 2 use the expanded schema.

## Work-item types

| Type | Created by | Consumed by | Key fields |
|------|-----------|-------------|------------|
| `feature` | Decomposer | Interface architect (via link) | `spec_section`, `priority`, `fr_ids` |
| `interface_spec` | Interface architect | Test author, Implementer | `spec_section`, `ac_ids`, `artifact_path` |
| `test_suite` | Test author | Implementer, Cross-family reviewer | `interface_ref`, `ac_coverage`, `artifact_path` |
| `implementation` | Implementer | Cross-family reviewer, Frontier judge | `interface_ref`, `test_suite_ref`, `artifact_path` |
| `review` | Runner (on behalf of reviewers) | Runner (routing logic) | `review_type`, `verdict`, `rationale` |
| `integration` | Integrator | Outcome verifier | `included_features`, `artifact_path` |

## Link types

| Link | Source → Target | Purpose |
|------|----------------|---------|
| `derived_from` | feature → feature | Decomposition DAG (dependency edges) |
| `has_interface` | feature → interface_spec | Which feature this interface serves |
| `has_tests` | interface_spec → test_suite | Which interface these tests target |
| `implements` | implementation → interface_spec | Which interface this code fulfills |
| `tested_by` | implementation → test_suite | Which tests validate this implementation |
| `reviews` | review → implementation | Which implementation is being reviewed |
| `integrates` | integration → implementation | Which implementations are included |
| `revision_of` | interface_spec → interface_spec | Tracks contract revision chain |

## Open design questions

1. **Review targets beyond implementation.** The `reviews` link type only supports `review → implementation`. Cross-family reviews of interface_specs or test_suites would need additional link types (`reviews_interface: review → interface_spec`, `reviews_tests: review → test_suite`). Deferred until Phase 2 exercises the review path.

2. **Per-type role gating.** Substrate's `allowed_roles` on transitions applies to all work-item types. There's no per-type role restriction. The runner must ensure the correct role claims each type. If this proves error-prone, substrate's FR-24 (actor roles enforcement) can be activated to gate at the database level.

3. **Outcome verification and principal review.** Stages 9 and 10 are not modeled as work-item types. They're runner-level orchestration that operates on the full set of locked work-items for a spec. If they need substrate-level tracking, add `outcome_verification` and `principal_review` work-item types in a future workflow version.

4. **Integration test gating.** The `integration` work-item passes through the same `gating` state, but the gates for integration are different (cross-cutting tests, not unit tests). The gate code is runner-side, so the workflow doesn't need to distinguish. The runner checks `work_item_type` and runs the appropriate gate suite.

5. **Hook-driven stage progression.** The runner should register async hooks on `gate_pass` and `gate_fail` transitions. A `gate_pass` hook on an `interface_spec` would create a `test_suite` work-item and link it. A `gate_pass` hook on a `test_suite` would create an `implementation` work-item. This is the hook-based stage triggering described in spec §4. The hook implementations are runner code; the workflow YAML only declares that hooks should fire on those transitions (via the `hooks` field on transitions, which would be added when the runner is built).
