---
number: "132"
title: Phase 4 jury and race architecture skeleton
severity: medium
status: implemented
kind: improvement
author: agent
-date: "2026-05-13"
tags: [phase-4, jury, race, runner, gate, scheduler, config]
related: ["120", "RFC-005", "RFC-007", "RFC-014"]
---

## Summary

Implemented the foundational architecture for Phase 4 multi-channel judge gates and A/B race patterns. The pipeline now structurally supports jury and cross-family review work-items, but Phase 4 is config-gated (`phase4_enabled` defaults to False) and not yet validated by a golden run.

## Changes

### Constants (`src/factory/constants.py`)

- Added Phase 4 identifiers:
  - Roles: `ROLE_CROSS_FAMILY_REVIEWER`, `ROLE_FRONTIER_JUDGE`, `ROLE_INTEGRATOR`, `ROLE_OUTCOME_VERIFIER`, `ROLE_COHERENCE_REVIEWER`
  - Work-item types: `WORK_ITEM_TYPE_REVIEW`, `WORK_ITEM_TYPE_JURY`, `WORK_ITEM_TYPE_INTEGRATION`, `WORK_ITEM_TYPE_OUTCOME_VERIFICATION`
  - Transitions: `TRANSITION_REVIEW_PASS`, `TRANSITION_REVIEW_FAIL`, `TRANSITION_JURY_PASS`, `TRANSITION_JURY_FAIL`, `TRANSITION_JURY_DISAGREE`
  - Gate names: `GATE_NAME_CROSS_FAMILY_REVIEW`, `GATE_NAME_JURY`, `GATE_NAME_JURY_QUORUM`, `GATE_NAME_JURY_DISAGREE`
  - Link types: `LINK_TYPE_REVIEWS`, `LINK_TYPE_JUDGES`
  - Custom fields: `CUSTOM_FIELD_REVIEW_REF`, `CUSTOM_FIELD_JURY_REF`
  - Artifact filename: `ARTIFACT_FILENAME_JURY_VERDICT`

### Workflow YAML (`workflows/phase4.yaml`)

- New work-item types: `review`, `jury`
- New roles: `cross_family_reviewer`, `frontier_judge`
- New link types: `reviews`, `judges`
- Transitions extended for review/jury pass/fail/disagree
- `attempt_threshold: 3` maintained

### FactoryConfig (`src/factory/config.py`)

- `FactoryConfig.phase4()` constructor added with:
  - `workflow_version=4`
  - `worker_roles` including `cross_family_reviewer` and `frontier_judge`
  - `type_to_role` mapping `review` and `jury` types
  - `roles` with default `ROLE_CROSS_FAMILY_REVIEWER` → OpenCode (K2) and `ROLE_FRONTIER_JUDGE` → Claude Code
  - `stage_topology`: `implementation` locked → `review` → `jury`
- `jury_quorum: int = 2` configurable field

### Jury module (`src/factory/jury.py`)

- `JurorVote` frozen dataclass: `passed`, `rationale`, `channel`, `family`
- `JuryVerdict` frozen dataclass: `passed`, `votes_for`, `votes_against`, `quorum_met`, `verdicts`, `disagreement_rationale`
- `run_jury(channels, prompt, outputs_dir, timeout, quorum)` invokes jurors sequentially, parses JSON votes, computes quorum, generates disagreement rationale when split.

### Review module (`src/factory/review.py`)

- `ReviewResult` frozen dataclass: `passed`, `rationale`, `findings`
- `run_review(channel, prompt, outputs_dir, timeout)` invokes cross-family reviewer, parses structured JSON output.

### Prompt templates

- `src/factory/prompts/cross_family_reviewer.md` — JSON output: `{"passed": bool, "findings": [...], "rationale": str}`
- `src/factory/prompts/frontier_judge.md` — JSON output: `{"passed": bool, "rationale": str}`

### Context derivation (`src/factory/context.py`)

- `derive_review_context()` resolves `interface_ref`, `test_suite_ref`, `implementation_ref` from linked work items and injects them into `extra_artifacts`.
- `derive_jury_context()` resolves the linked `review_ref` and reads its `interface_ref`, `test_suite_ref`, `implementation_ref` to build the jury prompt bundle.

### Runner (`src/factory/runner.py`)

- `_derive_role_context()` dispatches review/judge roles to new context functions.
- `_process_jury_work_item()` aggregates multi-channel jury votes, writes `jury_verdict.json`, submits with "jury_aggregate" channel metadata.
- `_resolve_jury_channels()` selects juror channels from `config.roles`.

### Gate layer (`src/factory/gate.py`)

- `evaluate_review(artifact_path)` parses JSON, returns `GateResult(passed=..., gate_name=cross_family_review)`.
- `evaluate_jury(artifact_path)` parses JSON verdict, checks `quorum_met`, returns `GateResult(passed=quorum_met)`.

### Gate process (`src/factory/gate_process.py`)

- Dispatcher extended for `WORK_ITEM_TYPE_REVIEW` → `evaluate_review()` and `WORK_ITEM_TYPE_JURY` → `evaluate_jury()`.

### Router (`src/factory/router.py`)

- Imports new transition constants (currently unused in routing logic; reserved for future expansion).

### Tests

- `tests/test_jury.py` with 10 tests:
  - `_parse_vote` edge cases
  - `run_jury` quorum met (2 of 3), quorum not met, unanimous against, channel failure, output dir per-channel, frozen dataclass integrity.

## Validation

- `make check` passes: 589 tests, 13 skipped, lint clean, audit clean.
- No existing tests broken.

## Race deferred

- A/B race patterns for load-bearing roles are defined in `spec.md` but not yet wired in runner. Parallel channel invocation is deferred to a follow-up session. See `plans/phase4-implementation.md` §11.

## Telemetry notes

- Jury artifacts carry `channel="jury_aggregate"` and `family="multi"` in actor metadata. Telemetry should be updated to treat this as a synthetic channel (not a real model channel) for pass-rate calculations. Deferred to RFC-005 (composable failure/escalation architecture).

## Related

- RFC-005: Composable failure/escalation architecture — Phase 4 jury disagreement routing needs to be integrated with the existing `route()` table instead of hardcoded jury-specific transitions.
- RFC-007: Test efficacy scoring via mutation testing gates — jury is a model-based substitute; both layers may coexist in Phase 5.
- BC-120: Implementer-initiated interface amendment — jury disagreement back to interface_architect provides the first automated trigger for BC-120.
