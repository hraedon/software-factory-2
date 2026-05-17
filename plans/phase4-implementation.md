# Phase 4 Implementation Plan

**Status:** obsolete — Phase 4 architecture shipped and exit-validated at GR-027 (cert-watch full DAG, dual-family jury). Phase 5 (GR-038) further validates jury under K2+Sonnet with N=4 quorum events. Retained for historical reference.
**Origin:** spec.md §10 Phase 4 — Jury and race.

## Scope

Implement the foundational architecture for multi-channel judge gates and A/B race patterns. Phase 4 does not need to be validated by a golden run in this session; the goal is to make the pipeline shape support jury and race, with tests.

## Components

### 1. Constants (`src/factory/constants.py`)

Add Phase 4 identifiers:
- `ROLE_CROSS_FAMILY_REVIEWER`, `ROLE_FRONTIER_JUDGE`, `ROLE_INTEGRATOR`, `ROLE_OUTCOME_VERIFIER`, `ROLE_COHERENCE_REVIEWER`
- `WORK_ITEM_TYPE_REVIEW`, `WORK_ITEM_TYPE_JURY`, `WORK_ITEM_TYPE_INTEGRATION`, `WORK_ITEM_TYPE_OUTCOME_VERIFICATION`
- `GATE_NAME_CROSS_FAMILY_REVIEW`, `GATE_NAME_JURY`, `GATE_NAME_JURY_QUORUM`, `GATE_NAME_JURY_DISAGREE`
- `TRANSITION_REVIEW_PASS`, `TRANSITION_REVIEW_FAIL`, `TRANSITION_JURY_PASS`, `TRANSITION_JURY_FAIL`, `TRANSITION_JURY_DISAGREE`
- `STATE_REVIEWING`, `STATE_JURYING` (or reuse `gating` with role-based dispatch)

Decision: Reuse `gating` state for review/jury to minimize workflow complexity. The gate_process already role-dispatches via `evaluate_*` functions. Add `evaluate_review()` and `evaluate_jury()`.

### 2. Workflow YAML (`workflows/phase4.yaml`)

Extend phase3.yaml with:
- New work-item types: `review`, `jury`
- New transitions: `review_pass`, `review_fail`, `jury_pass`, `jury_fail`, `jury_disagree`
- New roles: `cross_family_reviewer`, `frontier_judge`
- Link types: `reviews` (review → implementation), `judges` (jury → review)
- attempt_threshold: 3 (same)

### 3. FactoryConfig (`src/factory/config.py`)

Add:
- `jury_channels: tuple[str, ...]` — channel names for jurors
- `jury_quorum: int` — default 2
- `review_channel: str` — channel for cross-family reviewer
- `phase4_enabled: bool` — default False
- `race_channels: dict[str, tuple[str, ...]]` — role → channels to race
- New `StageHandoff` entries: `implementation` locked → `review`; `review` locked → `jury`

### 4. Jury module (`src/factory/jury.py`)

Dataclasses:
- `JurorVote(passed, rationale, channel, family)`
- `JuryVerdict(passed, votes_for, votes_against, quorum_met, verdicts, disagreement_rationale)`

Functions:
- `run_jury(channels, prompt, outputs_dir, timeout, quorum) -> JuryVerdict`
  - Invokes each channel sequentially (parallel deferred to Phase 4+ optimization)
  - Collects `InvocationResult` from each
  - Parses structured vote from each result
  - Checks quorum: `votes_for >= quorum` → passed
  - If no quorum and no unanimous against → `disagreement_rationale`

### 5. Review module (`src/factory/review.py`)

Dataclasses:
- `ReviewResult(passed, rationale, findings)`

Functions:
- `run_review(channel, prompt, outputs_dir, timeout) -> ReviewResult`
  - Thin wrapper around `channel.invoke()` + parsing structured review output

### 6. Prompt templates

- `src/factory/prompts/cross_family_reviewer.md` — Review skeleton + tests against AC + interface. Structured JSON output: `{"passed": bool, "findings": [...], "rationale": str}`
- `src/factory/prompts/frontier_judge.md` — "Do these tests, if they pass, demonstrate the AC is met?" Structured JSON output: `{"passed": bool, "rationale": str}`

### 7. Context derivation (`src/factory/context.py`)

Add:
- `derive_review_context(sub, work_item_id, spec_content) -> PromptContext`
- `derive_jury_context(sub, work_item_id, spec_content) -> PromptContext`

These resolve the linked `implementation`, `test_suite`, and `interface_spec` artifacts, plus the AC list, and build the prompt bundle.

### 8. Runner extension (`src/factory/runner.py`)

Extend `process_work_item()`:
- If `role_name == ROLE_CROSS_FAMILY_REVIEWER`: derive review context, invoke single channel, submit artifact
- If `role_name == ROLE_FRONTIER_JUDGE`: derive jury context, invoke `run_jury()` with configured channels, write aggregated `jury_verdict.json` artifact, submit

### 9. Gate process extension (`src/factory/gate_process.py`)

Extend `process_gate_item()` dispatch:
- `WORK_ITEM_TYPE_REVIEW`: call `evaluate_review()` — parses the review artifact JSON, checks `passed` field
- `WORK_ITEM_TYPE_JURY`: call `evaluate_jury()` — parses the jury verdict JSON, checks `quorum_met`

### 10. Scheduler extension (`src/factory/scheduler.py`)

Extend `stage_topology` in `FactoryConfig.phase4()`:
- `StageHandoff(source_type=implementation, source_state=locked, target_type=review, link_type=reviews, ref_field=implements)` — or similar
- `StageHandoff(source_type=review, source_state=locked, target_type=jury, link_type=judges, ref_field=reviews)`

### 11. Race support (deferred to later in Phase 4)

The spec mentions A/B race for load-bearing roles. Implementing this requires parallel channel invocation in the runner. For the initial Phase 4 skeleton, race is defined in config but not yet wired in runner. File an RFC or note in AGENTS.md.

### 12. Tests

New test files:
- `tests/test_jury.py` — JuryVerdict logic, quorum edge cases, tiebreaker behavior
- `tests/test_review.py` — ReviewResult parsing
- `tests/test_phase4_pipeline.py` — Pipeline shape: scheduler creates review after impl locks; runner dispatches review/judge roles
- `tests/test_context_phase4.py` — Context derivation for review/judge
- Update `tests/test_phase3.py` to cover phase4 config

### 13. Documentation

- Update `AGENTS.md` with Phase 4 status
- Add worklog entry
- Update `spec.md` §10 to note Phase 4 in progress

## Exit criteria for this session

- [ ] `phase4.yaml` workflow exists and passes schema validation (via `populate_work_items.py` smoke test)
- [ ] Constants include all Phase 4 identifiers
- [ ] `FactoryConfig.phase4()` constructor exists with jury/review settings
- [ ] `jury.py` and `review.py` modules exist with core logic and tests
- [ ] Prompt templates exist for `cross_family_reviewer` and `frontier_judge`
- [ ] Context derivation extended for review/judge
- [ ] Runner handles `cross_family_reviewer` and `frontier_judge` roles
- [ ] Gate process handles `review` and `jury` work-item types
- [ ] Scheduler creates `review` after `implementation` locks, `jury` after `review` locks (when Phase 4 enabled)
- [ ] All existing tests still pass; new tests added
- [ ] Lint clean

## Notes

- **Minimal intrusion:** Do not change Phase 1–3 pipeline shape. Phase 4 is additive.
- **Config-gated:** `phase4_enabled` defaults to False. Existing configs continue to work unchanged.
- **Sequential jury for now:** `run_jury()` invokes jurors sequentially to avoid subprocess parallelization complexity. Parallel invocation can be added later without changing the interface.
- **Structured output parsing:** Both review and jury expect JSON artifacts. The gate parses these with `json.JSONDecoder.raw_decode` (same pattern as output extraction).
