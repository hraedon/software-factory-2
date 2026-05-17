# Phase 2 Implementation Plan — Sequential single-channel pipeline

**Status:** obsolete — Phase 2 complete (GR-004/005/006a). Sequential pipeline has since been extended through Phases 3–5. Retained for historical reference.
**Author:** claude-opus-4-7
**Date:** 2026-05-07

## Goal

Get a four-stage sequential pipeline (`interface_architect → test_author → implementer → mechanical_gate`) running end-to-end against a single channel (Claude CC), per `spec.md` §10 Phase 2. Single channel still — fleet integration is Phase 3, jury/race is Phase 4. Establish the per-(role, channel) telemetry shape end-to-end so Phase 3 has a baseline to measure against.

## Exit criteria

1. A factory worker + gate process pair can drive an `interface_spec → test_suite → implementation` chain to `locked` end-to-end without human intervention, with substrate hooks (or polling) coordinating the inter-stage handoff.
2. **Primary set (10 items, reused from golden-run-001):** ≥80% first-attempt full-pipeline pass; ≥95% within retry budget. The lower first-attempt bar vs. Phase 1's 90% reflects the multiplicative cost of compounding stage failures over four stages.
3. **Secondary LoB set (3 items, reused/extended from Phase 1):** ≥2/3 within retry budget.
4. **Routing-stress items (2 items, new):** intentionally constructed to fail the implementation gate on first attempt; pass after one round-trip through the `gate_fail → implementer` loop, demonstrating routing recovery within the retry budget.
5. **Adversarial item:** still returns `cannot_proceed` at the `interface_architect` stage (Phase 1 behavior preserved).
6. **Replay:** `tests/test_golden_run_002.py` reproduces the recorded run with byte-identical context bundles per (work-item, role) and identical sequence of substrate transitions.
7. **Telemetry:** `report.py` (extended) emits a `(role, channel, gate) → first-attempt pass-rate` table from substrate events for the primary set.
8. Idempotency: kill-and-restart at every stage of every role's loop without artifact corruption or duplicate events. Per-stage tests in `test_runner_idempotency.py` extended to cover all three worker roles.

## Prerequisites

### Pre-wave work — verified 2026-05-07

The DeepSeek session prior to this plan landed three pre-wave changes that are now verified usable. They are uncommitted on `main` as of 2026-05-07; commit them before Wave 1 starts.

| Item | File(s) | Status |
|---|---|---|
| `channel_fail` events surface in `derive_failures()` | `src/factory/failure_summary.py`, `src/factory/context.py` | ✅ Implemented; tests added in `tests/test_failure_summary.py`. |
| Conditional routing via `DiagnosticKind` enum + dispatch table | `src/factory/router.py`, `src/factory/gate.py`, `src/factory/gate_process.py` | ✅ Implemented as a declarative dispatch table keyed by `DiagnosticKind`. Cleaner than a per-`Route` `condition` callback; preserved as the canonical mechanism in this plan. Currently only contains Phase 1 entries (all routes → `interface_architect`); Wave 5 extends it. |
| `phase2.yaml` workflow round-trip against substrate | `workflows/phase2.yaml` | ✅ Registers cleanly via `register_workflow_file`. States, transitions (`claim`, `submit`, `gate_pass`, `gate_fail`, `channel_fail`, `release`, `cannot_proceed`), roles (`interface_architect`, `test_author`, `implementer`, `mechanical_gate`), work-item types (`interface_spec`, `test_suite`, `implementation`), link types (`implements`, `tested_by`, `derived_from`), and `attempt_threshold: 3` all validated. |

**Tests:** 138/138 pass with these changes (up from 125 at Phase 1 exit); 1 skip is the existing adversarial integration test.

**Caveats to address in the build:**
- `_PHASE2_DISPATCH` is named for Phase 2 but populated with Phase 1 entries only. Wave 5 must add real entries for test-suite gate kinds and implementation gate kinds.
- `phase2.yaml`'s single `gate_fail: gating → new` transition keeps the workflow simple but pushes role-aware re-routing entirely into the runner/router. The workflow does not enforce "after a test_suite gate_fail, only test_author can re-claim" — that discipline is in `router.route()` and the runner's claim-filter. Acceptable for Phase 2; revisit if Phase 4's jury work surfaces a need for stricter workflow-level guarantees.
- `derive_failures()` aggregates `channel_fail` events, but the router's `channel_fail` route is currently unreached because workers emit `channel_fail` via `append_event` rather than `transition`. Wave 0 should reconcile: either move `channel_fail` to a real transition (it exists in `phase2.yaml`) or remove the dead route from `router.py`. Recommended: move to a real transition; the workflow already supports it.

### External prerequisites

| Item | Where | Why blocking |
|---|---|---|
| Substrate ref-type validation for `interface_ref` / `test_suite_ref` | substrate | If substrate does not enforce that `target_work_item_type: interface_spec` references actually point at an `interface_spec` work-item, Wave 1 must add validators. Verify before Wave 1; file a substrate breadcrumb if missing. |
| Substrate hooks reliability (BC-021 in substrate) | substrate | Phase 2 has multi-stage handoff; a missed hook can stall a pipeline. Polling fallback acceptable as Phase 2 mitigation, but BC-029 (events-since cursor) is a soft prerequisite. |

## Build order

Eight waves. Each wave ends with a runnable, testable artifact. Total estimate: 10–14 days.

### Wave 0 — Pre-wave commit + reconciliation (½ day)

- Commit the pre-wave changes (`failure_summary.py`, `router.py`, `gate.py`, `gate_process.py`, `context.py`, the new tests, `workflows/phase2.yaml`, the resolved-breadcrumb moves) in one or two clean commits.
- Reconcile `channel_fail` event mechanism: switch worker emission from `append_event` to `transition` using the workflow's `channel_fail` transition. Update `runner.py:_handle_invoke_failure` and the corresponding test in `test_channel_failures.py`.
- Add a `test_phase2_workflow_roundtrip.py` test that registers `workflows/phase2.yaml` against a fresh substrate project as a regression guard.
- Confirm 138/138+ pass.

**Done when:** changes committed, `channel_fail` is a real transition, workflow round-trip is in CI.

### Wave 1 — Gate expansion (1.5 days)

Extend `gate.py` to evaluate the two new artifact types.

- `evaluate_test_suite(artifact_path, ac_ids, interface_ref_pyi_path) -> GateResult`:
  - Parses as Python, no syntax errors.
  - `pytest --collect-only` succeeds (tests are discoverable).
  - All declared `ac_ids` referenced in test docstrings or markers (reuses BC-016 lesson — no substring search; structural binding via decorator/parametrize/docstring scan).
  - Imports only the locked interface module, not implementation. Detects cross-module imports of `_impl` or unrelated modules.
- `evaluate_implementation(artifact_path, test_suite_path, interface_pyi_path) -> GateResult`:
  - Imports cleanly.
  - `mypy --strict` against the locked `.pyi` (signature conformance — the contract).
  - `pytest` against the test suite, all tests pass.
  - `ruff check` passes (configurable rule set, default minimal).
  - Diagnostics structured per failing gate, with `diagnostic_kind` set so the router can dispatch.
- New `DiagnosticKind` values: `TEST_AC_BINDING`, `TEST_COLLECT`, `TEST_IMPORT_FORBIDDEN`, `IMPL_MYPY`, `IMPL_PYTEST`, `IMPL_LINT`, `IMPL_IMPORT`.
- `tests/test_gate_test_suite.py`: happy + 4 failure modes.
- `tests/test_gate_implementation.py`: happy + 5 failure modes.

**Done when:** new gates run with hand-crafted artifacts; diagnostics carry the right kind; the existing `evaluate_interface_spec` is unchanged.

### Wave 2 — `test_author` role (1 day)

- `factory/prompts/test_author.md` — static markdown role prompt; hash recorded in `actor_metadata.prompt_hash`. Inputs to render: spec section + AC list + locked `.pyi` content + glossary excerpt + prior failures (gate_fail + channel_fail).
- `context.derive_test_author_context(substrate, work_item_id) -> PromptContext`:
  - Resolves `interface_ref` work-item; reads its `artifact_path`; loads the `.pyi` content from disk and validates manifest hash matches `artifact_hash`.
  - Pure function; same substrate state → byte-identical bundle.
- `tests/test_context_test_author.py`: determinism + bundle-shape + interface_ref-resolution + missing-interface-ref-error.

**Done when:** context bundle is byte-deterministic and consumable by a stub runner.

### Wave 3 — `implementer` role (1 day)

- `factory/prompts/implementer.md` — static markdown.
- `context.derive_implementer_context(substrate, work_item_id) -> PromptContext`:
  - Resolves both `interface_ref` and `test_suite_ref`; reads both artifacts; validates manifest hashes.
  - Includes prior failures (gate_fail + channel_fail) so the implementer sees why a previous attempt's mypy/pytest run failed.
- `tests/test_context_implementer.py`: determinism + both-refs-resolution + prior-failures-included + missing-test-suite-ref-error.

**Done when:** ditto.

### Wave 4 — Multi-stage runner + hooks-driven handoff (2 days)

The architectural-risk wave. Begin with a half-day spike to validate the multi-stage shape before committing to the rest.

#### Spike (½ day)

Drive a single work-item `interface_spec` to `locked`, then verify the `tests_authored` hook (or polling) schedules the corresponding `test_suite` work-item correctly. Use `MockChannel` and `MockSubstrate`. The spike is to answer: does the existing single-role runner generalize, or does inter-stage handoff need a different scheduler shape? Decision lives in a short breadcrumb at the end of the spike.

#### Implementation (1.5 days)

- `runner.py` extension: register multiple worker roles per process via config. Default: one process per role-set (`interface_architect` only, `test_author` only, `implementer` only) so kill-radius and telemetry stay clean. The runner's claim filter respects the process's registered role set.
- Hook-driven scheduling: when an `interface_spec` work-item transitions to `locked`, a substrate hook creates a `test_suite` work-item linked via `derived_from`. Likewise `test_suite → locked` schedules `implementation` linked via `tested_by` + `implements`. Hook configuration lives in the workflow YAML or alongside it; this is the first SF2 use of substrate hooks beyond Phase 1's polling fallback.
- Polling fallback for missed hooks (per spec §9 substrate-as-spine principle): every N seconds, scan for items in expected states whose downstream items don't yet exist. Defensive; logs a warning when it fires.
- Resume semantics: each role's worker resumes from its own attempt manifest (Phase 1 mechanics extended per role); inter-stage handoff is naturally idempotent because work-items are created via substrate transitions (deduplicated by event_id).
- `tests/test_pipeline_smoke.py`: spawn three worker processes + one gate process; create one `interface_spec` work-item; assert all three downstream artifacts produced and locked.
- `tests/test_pipeline_resume.py`: kill each worker process at each substage of its loop; assert resume.

**Done when:** smoke + resume tests green for all three role-sets coordinated through substrate; no orphaned work-items after kill scenarios.

### Wave 5 — Phase-2 routing (1 day)

Extend `_PHASE2_DISPATCH` with the new `DiagnosticKind` entries from Wave 1.

- `IMPL_PYTEST` → `implementer` (most common case: tests fail, implementation needs revision).
- `IMPL_MYPY` → `implementer`.
- `IMPL_LINT` → `implementer`.
- `IMPL_IMPORT` → `implementer`.
- `TEST_AC_BINDING` → `test_author`.
- `TEST_COLLECT` → `test_author`.
- `TEST_IMPORT_FORBIDDEN` → `test_author` (test reached past the locked interface).
- Cross-stage escalation: if the same role+kind has failed `attempt_threshold` times (3 by default), escalate to `interface_architect` with a `cannot_proceed_seam` diagnostic (per spec §4 "ambiguous contract" failure mode). Honors the spec's "errors loop back to contract revision, not worker retry" principle.
- `tests/test_router_phase2.py`: each new dispatch entry + the escalation case.

**Done when:** `_PHASE2_DISPATCH` is no longer Phase-1-only and the escalation path is tested.

### Wave 6 — Pipeline integration + idempotency hardening (1.5 days)

- `tests/test_pipeline_integration.py` against a real substrate (docker-compose-test Postgres) + `MockChannel`:
  - Drive a curated 3-item subset end-to-end through all four stages.
  - Failure injection: `MockChannel.scripted_failure(stage="implementer", attempt=1)` then succeed at attempt 2. Assert routing back to `implementer`, retry, recovery.
  - Cross-stage escalation: scripted failures at attempts 1, 2, 3 in `implementer`; assert escalation to `interface_architect` with `cannot_proceed_seam` diagnostic.
- `tests/test_pipeline_idempotency.py`: kill-and-restart at every stage of every role's loop. Reuses BC-003 mechanics extended per role.
- `MockSubstrate` audit: confirm new transitions, hooks, and ref-type validators are honored; close any divergence with substrate. Per the 2026-05-07 reflection, this is a known liability — schedule a half-hour MockSubstrate review before declaring this wave done.

**Done when:** integration + idempotency tests green; MockSubstrate audit committed.

### Wave 7 — Curated Phase-2 test set + golden-run-002 (2–3 days, plateau-handled)

#### Test set composition

Reuse the Phase 1 fixtures, extending each work-item to also produce `test_suite` and `implementation` artifacts.

**Primary set (10 items):** the golden-run-001 substrate-spec items, extended to full pipeline. Same 3-shape distribution (pure-interface, error-taxonomy, ADT-validation) preserved.

**Secondary LoB set (3 items):** the existing LoB-flavored items (CSV-to-typed-records, etc.), extended to full pipeline.

**Routing-stress items (2 items, new):**
- One designed to elicit a `mypy` failure on first attempt (e.g., a contract that rewards a type-narrowing implementation but invites a naive pass-through). Pass criterion: routes back to `implementer`, succeeds on attempt 2.
- One designed to elicit a `pytest` failure on first attempt (e.g., off-by-one boundary case clearly required by AC but easy to skip). Pass criterion: ditto.
- These items intentionally stress the loop. Their pass criterion is *recovery-within-budget*, not first-attempt pass.

**Adversarial item (1, unchanged from Phase 1):** ambiguous AC; expected to return `cannot_proceed` at the `interface_architect` stage; never reaches test_author or implementer.

#### Recording and replay

- Run all 16 items through the real `ClaudeCodeChannel` end-to-end. Record artifacts + manifests + substrate event dumps into `tests/fixtures/golden-run-002/`.
- `tests/test_golden_run_002.py`: replays with `MockChannel` + `MockSubstrate`; asserts byte-identical context bundles per (work-item, role); asserts identical substrate transition sequence.

#### Plateau handling

Carry forward the Phase 1 budget: 3 prompt revisions max per role. If after 3 revisions the bar is not met:

1. Stop iterating prompts.
2. Diagnose by category: spec ambiguity / role scope / channel mis-suited / gate too strict.
3. Open a breadcrumb with concrete examples.
4. Surface to principal — Phase 2 exit is a decision point, not a forced ship.

The bar exists to protect Phase 3. Phase 3 expands the channel set; if Phase 2's single-channel baseline is shaky, every channel addition compounds noise.

**Done when:** golden-run-002 green AND all exit criteria met AND prompt revisions (if any) committed with rationale.

### Wave 8 — Telemetry reporter skeleton (1 day)

- Extend `report.py` to read substrate events across all work-items in a project and produce:
  - `(role, channel, work_item_type) → first-attempt pass rate`.
  - `(role, channel) → mean attempts to pass`.
  - `(role, channel, gate_name) → gate-failure breakdown`.
  - `(role, channel) → mean wall-clock per attempt` (using event timestamps).
- Output: a markdown table dumped to stdout and a JSON sidecar for downstream tooling.
- Does not run automatically. Invoked manually after a run; structure is what matters for Phase 3.
- `tests/test_report.py`: small fixture run; assert the produced table matches expected counts.

**Done when:** running `python report.py --project sf2_test` after the golden run produces a sensible per-(role, channel) table.

## Test strategy summary

- **Unit:** workspace, gate (all four `evaluate_*` functions), router (full dispatch table), failure_summary, context (all three derivers). No substrate or model dependencies.
- **Integration:** pipeline smoke + integration + idempotency against real substrate (docker-compose-test) with `MockChannel`.
- **Acceptance:** golden-run-002 with real Claude CC for fixture creation, `MockChannel` for replay. The first-attempt-pass-rate measurement is the only test requiring live Claude CC at runtime.

## Out of scope for Phase 2 (explicitly deferred)

- Channel adapters for K2, GLM, DeepSeek, Gemini (Phase 3).
- Multi-channel jury gates (Phase 4).
- Race patterns (Phase 4).
- Stage 6 cross-family review (Phase 3+, requires multi-channel).
- Stage 7 frontier judge / jury (Phase 4).
- Stage 0 socratic-specification integration (still reads pre-existing spec.md).
- Stage 8/9/10 (integration, outcome verification, principal review).
- Hot-reloadable config (still cold-load at startup).
- Outcome dashboard / web UI.

## Open questions to resolve before Wave 4

1. **Spike outcome:** does the single-process-per-role pattern hold, or does Phase 2 need a different scheduler? Decision lives in Wave 4's spike breadcrumb.
2. **Substrate hooks vs. polling:** prefer hooks if substrate's BC-021 is closed at Phase 2 start; else polling fallback is the primary mechanism with hooks layered in later. Decide at Wave 4 kickoff based on substrate state.
3. **`mypy --strict` against `.pyi`:** the locked interface should be the type contract. Confirm `mypy` can be pointed at a separate stub file and treat the `.py` implementation as the module under check. Quick spike in Wave 1 if uncertain.
4. **Workspace layout for multi-stage artifacts:** Phase 1 used `<workspace>/<work_item_id>/attempt-NNNN/<artifact_name>`. Phase 2 has multiple linked work-items; resolve refs by reading the *target* work-item's `artifact_path` (already in the workflow YAML). Confirm this works across runner restarts and is consistent with `find_resumable_artifact`.

## Estimated total

10–14 days of focused work, assuming pre-wave commit lands cleanly and Wave 4 spike resolves the scheduler question without forcing a rewrite. Wave 7 is variable: a clean prompt run is ~2 days; a full plateau-handling cycle is ~3 days. Wave 4's spike is the single largest risk to the estimate.

## After Phase 2

Phase 3 starts only when:
- Phase 2 exit criteria are met sustainably (not "passed once").
- Telemetry reporter (Wave 8) has produced at least one full pass-rate table for the primary set, establishing the baseline against which channel additions will be measured.
- A short Phase-3-prep audit, mirroring the Phase 1 → Phase 2 audit, is opened as breadcrumbs.

The single most important Phase 2 → Phase 3 handoff artifact is the **first-attempt pass-rate baseline per (role, gate, work-item shape)**. Without it, "K2 is good enough at the implementer role" is a vibe; with it, it's a comparison against a recorded Claude-only baseline.
