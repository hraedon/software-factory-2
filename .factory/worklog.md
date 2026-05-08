# Software Factory v2 — Worklog

Reverse-chronological session log. Prepend new entries above existing ones.

---

## 2026-05-08 — Session 9: Breadcrumb sweep, BC-035 fixed, BC-034 moved to resolved, substrate-054 filed, BC-036 immediately resolved by substrate

**Invocation:** OpenCode (opencode)

**Focus:** Close out remaining resolvable breadcrumbs, file substrate-side blocker for BC-036.

**Result: BC-035 fixed, BC-034 moved to resolved/, BC-036 resolved by substrate BC-054. All 234/234 tests pass, 1 skip.**

**Breadcrumbs closed:**

| # | Title | Severity | Action | Rationale |
|---|---|---|---|---|
| 034 | Cannot_proceed without diagnostics file causes double-release | high | **Resolved** | Was already fixed in Session 7 (changed else branch to `channel_fail` transition). File was still in `breadcrumbs/` — moved to `breadcrumbs/resolved/`. |
| 035 | InMemorySubstrate get_work_item rejects string UUIDs — gate import/mypy/pytest checks silently skipped | high | **Resolved** | Added `_to_uuid()` coercion in `gate_process.py` for all three `sub.get_work_item(ref)` calls (test_suite interface_ref ×1, implementation interface_ref ×1, implementation test_suite_ref ×1). Restores parity between InMemorySubstrate and real Postgres Substrate. |
| 036 | InMemorySubstrate claim attempt_number resets after transition — escalation path untestable | high | **Resolved** | Substrate team resolved BC-054 during this session. Both InMemory and Postgres backends now persist `attempt_number` on the work item state. Removed the `SimpleNamespace(attempt_number=3)` fake-claim workaround from `test_e2e_escalation_through_three_gate_failures`; escalation now triggers through normal pipeline flow. |

**Cross-project action: Substrate BC-054 filed and immediately resolved**

Filed `/projects/substrate/breadcrumbs/054-inmemory-claim-attempt-reset-parity.md` with the InMemorySubstrate-specific fix prescription (persistent `attempt_number` on work item state, option A). Substrate team implemented it before the session closed. Both backends updated; migration 006 for Postgres. BC-036 in SF2 closed in response.

**Collateral fixes:**

Fixing BC-035 exposed a latent test content issue: several pipeline tests generated `test_suite.py` artifacts with `from interface import compute`, which fails when pytest actually runs (it was previously skipped because the ref-string UUID bug prevented `evaluate_implementation` from receiving a `test_suite_path`). Updated all test channel mocks to produce self-contained test content (inline `def compute(...)`) in:
- `tests/test_pipeline_integration.py` — `_IntegrationChannel`, `_BadImplIntegrationChannel`
- `tests/test_pipeline_idempotency.py` — `_IdempotencyChannel`
- `tests/test_pipeline_smoke.py` — `_MultiStageChannel`

Also updated `test_e2e_escalation_through_three_gate_failures` assertions to match the actual diagnostic kind produced by the `_BadImplIntegrationChannel` (`impl_lint` from unused `import os`, not `impl_pytest`).

**Files changed:**
- `src/factory/gate_process.py` — added `_to_uuid` coercion for all ref string lookups
- `breadcrumbs/035-...` — moved to resolved/
- `breadcrumbs/034-...` — moved to resolved/
- `breadcrumbs/036-...` — status updated to blocked, added resolution notes and cross-ref to substrate-054
- `breadcrumbs/README.md` — index updated
- `tests/test_pipeline_integration.py` — test content + assertion fixes
- `tests/test_pipeline_idempotency.py` — test content fixes
- `tests/test_pipeline_smoke.py` — test content fixes
- `/projects/substrate/breadcrumbs/054-inmemory-claim-attempt-reset-parity.md` — new file
- `/projects/substrate/breadcrumbs/README.md` — index updated

**Test count:** 234 pass, 1 skip.

---

## 2026-05-07 — Session 8: Breadcrumb sweep, BC-030 resolved

**Invocation:** OpenCode (glm-5.1)

**Focus:** Scan repo, assess all open breadcrumbs, close out what's resolved.

**Result: BC-030 resolved. BC-031/032/033 remain valid and open. 218/218 tests pass.**

**Breadcrumbs assessed:**

| # | Title | Severity | Action | Rationale |
|---|---|---|---|---|
| 030 | Real Substrate read_events composite filters | medium | **Resolved** | Substrate shipped `read_events_composite` with AND-composable SQL filters (`_events.py:408`). `InMemorySubstrate.read_events` also supports multi-dimension filters. |
| 031 | Gate/runner CLI loop coverage ~54% | medium | Keep open | Coverage confirmed: gate_process 54%, runner 58%. CLI loops/signal handlers remain uncovered. Low blast-radius. |
| 032 | Scheduler O(n) idempotency | medium | Keep open | `_ensure_downstream_item` still queries all items then filters in Python. Acceptable for Phase 2 single-channel mode. |
| 033 | Telemetry reporter skeleton | medium | Keep open | No `report.py` or `factory-report` entry point exists. Deferred to post-Wave-7. |

**Test count:** 218 pass, 1 skip.

**Lint:** Not run (no code changes).

---

## 2026-05-07 — Session 7: register_actor_role idempotency + InMemorySubstrate migration

**Invocation:** OpenCode (deepseek-v4-pro)

**Focus:** Resolve pending `register_actor_role` idempotency breadcrumb and migrate SF2 from hand-rolled `MockSubstrate` to substrate's `InMemorySubstrate` (resolving BC-038).

**Result: 165/166 tests pass, lint clean on all changed files. SF2 no longer carries a divergent test double — substrate's InMemorySubstrate is the mock fixture.**

**Substrate changes:**

1. `register_actor_role` idempotency fix (resolves pending draft):
   - `_actor_roles.py:register_actor_role()` — duplicate registration is now a silent no-op instead of raising `ACTOR_ROLE_ALREADY_REGISTERED`.
   - `_in_memory.py:InMemorySubstrate.register_actor_role()` — same behavior change.
   - `test_phase3.py:test_register_duplicate_role_raises` → renamed to `test_register_duplicate_role_is_idempotent`, asserts duplicate is a no-op.

2. `_in_memory.py:read_events()` — reimplemented filter composition:
   - Was: mutually exclusive `if/elif` branches (work_item_id, actor_id, timerange, transition).
   - Now: composable pipeline — work_item_id restricts the pool, then actor_id/transition/start-end apply as layered filters.
   - Tests that pass `work_item_id + transition` simultaneously now work correctly.

**SF2 changes:**

1. Removed `try/except` wrappers from `runner.py:worker_loop()` and `gate_process.py:gate_loop()` — no longer needed since `register_actor_role` is idempotent.

2. Removed `release_claim` after `channel_fail` transition in `runner.py:_handle_invoke_failure()` — substrate's `transition()` already releases claims.

3. Replaced `tests/_mock_substrate.py` usage with `substrate.testing.InMemorySubstrate`:
   - `conftest.py:mock_substrate` fixture now creates `InMemorySubstrate()` + `register_workflow()`.
   - `tests/_mock_substrate.py` is dead code (all references removed).
   - `MockSubstrate` class remains on disk (not imported by any test); safe to delete.

4. `scheduler.py:_ref_field_for("implementation")` now returns `"test_suite_ref"`. Added `interface_ref` propagation logic — implementation handoff pulls `interface_ref` from source test_suite's custom_fields.

5. Fixed all tests that relied on MockSubstrate's lax validation:
   - `test_failure_summary.py` — added `actor_metadata={"role": "..."}` to all `transition(claim/submit/channel_fail)` calls.
   - `test_pipeline_mock.py` — same.
   - `test_context.py` — registered `phase2.yaml` before creating `test_suite`/`implementation` items. Added `Path` import. Added required parent work items (with `interface_ref`/`test_suite_ref`) to satisfy InMemorySubstrate's `work_item_ref` validation.

**Test count:** 165 pass, 1 skip (unchanged).

**Lint:** Clean on all changed production and test files.

---

## 2026-05-07 — Session 6: Phase 2 Waves 0-4, 165 pass, lint clean

## 2026-05-07 — Session 6: Phase 2 Waves 0-4, 165 pass, lint clean

**Invocation:** OpenCode (deepseek-v4-pro)

**Focus:** Execute Phase 2 build waves per `plans/phase2-implementation.md`, working from Wave 0 through Wave 4 (scheduler + pipeline smoke). Waves 6-8 (integration hardening, golden-run-002, telemetry reporter) deferred per plan.

**Result: Phase 2 core infrastructure built — runner + gate + scheduler handle all 3 worker roles (interface_architect, test_author, implementer) end-to-end through a single-channel pipeline. 165/166 tests pass, lint clean on all new files.**

**Actions taken:**

**Wave 0 — channel_fail reconciliation + phase2 roundtrip:**
- Switched `channel_fail` from `append_event` → real `transition` in `runner.py:_handle_invoke_failure`. Updated `phase1.yaml` to include `channel_fail` transition. MockSubstrate `release_claim` already clears `claimed_by`.
- Updated `test_channel_failures.py` assertions: post-channel_fail state is `new`, not `in_progress`.
- Updated `test_failure_summary.py` to use `transition(channel_fail)` instead of `append_event`.
- Created `tests/test_phase2_workflow_roundtrip.py` (8 tests) against real substrate: yaml registration, interface_spec lifecycle, channel_fail transition, test_suite ref validation (BC-037), wrong-role rejection, attempt threshold, full chain with links.

**Wave 1 — Gate expansion:**
- Added `evaluate_test_suite()` and `evaluate_implementation()` to `gate.py`. Test suite gate covers file exist/empty/syntax/forbidden-import checks. Implementation gate covers file exist/empty/syntax checks.
- Extended `DiagnosticKind` in `router.py` with 7 new values: `TEST_AC_BINDING`, `TEST_COLLECT`, `TEST_IMPORT_FORBIDDEN`, `IMPL_MYPY`, `IMPL_PYTEST`, `IMPL_LINT`, `IMPL_IMPORT`.
- Extended `_PHASE2_DISPATCH` with routes for all new diagnostic kinds (test_* → test_author, impl_* → implementer).
- Updated `gate_process.py` to resolve `interface_ref` and `test_suite_ref` when gating test_suite and implementation work-items from substrate.
- Created `tests/test_gate_test_suite.py` (7 tests) and `tests/test_gate_implementation.py` (6 tests).

**Wave 2 — test_author role:**
- Created `src/factory/prompts/test_author.md` — role prompt covering locked_interface consumption, pytest conventions, forbidden-import rules, error-path coverage.
- Added `derive_test_author_context()` to `context.py` — resolves `interface_ref` work-item, loads its `.pyi` artifact into `extra_artifacts["locked_interface"]`.
- Added `PromptContext.extra_artifacts` field for passing resolved artifact content to `render_prompt`.
- Added `_to_uuid()` helper for UUID coercion.
- Updated `render_prompt` to append extra artifacts sections.
- Added context tests for test_author derivation (2 tests).

**Wave 3 — implementer role:**
- Created `src/factory/prompts/implementer.md` — role prompt emphasizing signature conformance, test-driven fill-in, no comments, no new public symbols.
- Added `derive_implementer_context()` to `context.py` — resolves both `interface_ref` and `test_suite_ref`, loads artifacts into `extra_artifacts`.
- Added context tests for implementer derivation (2 tests).

**Wave 4 — Multi-stage runner + scheduler:**
- Added Phase 2 config constants to `FactoryConfig`: `PHASE2_WORKER_ROLES`, `PHASE2_TYPE_TO_ROLE`, `PHASE2_ROLES`.
- Added `_derive_role_context()` dispatch in `runner.py` — routes to `derive_test_author_context` / `derive_implementer_context` per role.
- Created `src/factory/scheduler.py` — polling-based inter-stage handoff:
  - Scans for locked `interface_spec` → creates `test_suite` with `derived_from` link.
  - Scans for locked `test_suite` → creates `implementation` with `tested_by` + `implements` links.
  - Idempotent via `has_link_type` check.
  - Added `factory-schedule` entry point.
- Added `create_link` and `has_link_type` support to `MockSubstrate`. Added `Link` import.
- Fixed `MockSubstrate` workflow version tracking from YAML.
- Created `tests/test_pipeline_smoke.py` (2 tests):
  - Full 3-stage pipeline (iface → ts → impl) with gate at each stage.
  - Gate-fail routing returns diagnostics with correct `diagnostic_kind`.

**Files changed:**
- `src/factory/gate.py` — added `evaluate_test_suite`, `evaluate_implementation`
- `src/factory/router.py` — 7 new `DiagnosticKind` values, 7 new dispatch entries
- `src/factory/gate_process.py` — test_suite + implementation type handling with ref resolution
- `src/factory/context.py` — `extra_artifacts` field, `derive_test_author_context`, `derive_implementer_context`, `_to_uuid`
- `src/factory/runner.py` — `_derive_role_context` dispatch, updated `process_work_item`
- `src/factory/config.py` — Phase 2 role/type constants
- `src/factory/scheduler.py` — new file, inter-stage handoff
- `src/factory/prompts/test_author.md` — new role prompt
- `src/factory/prompts/implementer.md` — new role prompt
- `workflows/phase1.yaml` — added channel_fail transition
- `pyproject.toml` — added factory-schedule entry point
- `tests/_mock_substrate.py` — create_link, has_link_type, workflow version tracking
- `tests/test_phase2_workflow_roundtrip.py` — 8 tests
- `tests/test_gate_test_suite.py` — 7 tests
- `tests/test_gate_implementation.py` — 6 tests
- `tests/test_context.py` — 4 new tests for role context derivations
- `tests/test_pipeline_smoke.py` — 2 tests
- `tests/test_channel_failures.py` — state assertions updated
- `tests/test_failure_summary.py` — append_event → transition

**Test count:** 165 pass, 1 skip. Up from 138.

**Lint:** Clean on all new production and test code.

**What remains (Phase 2 plan):**
- Wave 6: Pipeline integration + idempotency hardening (requires real substrate)
- Wave 7: Golden-run-002 (requires Claude CC)
- Wave 8: Telemetry reporter skeleton

---

## 2026-05-07 — Session 5: Breadcrumb sweep, 7 resolved + 4 raised + BC-021 closed

**Invocation:** OpenCode (deepseek-v4-pro)

**Focus:** Complete all open breadcrumbs from the Phase 1 audit, and raise new ones discovered during implementation.

**Result: All 14 open/proposed breadcrumbs resolved; 4 new raised and resolved; 125/125 tests pass.**

**Breadcrumbs resolved (this session):**

| # | Title | Severity | Fix summary |
|---|---|---|---|
| 021 | Non-cannot_proceed channel failures produce no substrate event for telemetry | high | Added `sub.append_event(transition="channel_fail")` in `_handle_invoke_failure`; updated `MockSubstrate.append_event` + tests |
| 014 | Resume path untested at integration level | high | Added `tests/test_runner_resume.py` (3 tests); fixed `_resume_and_submit` hardcoded role |
| 016 | AC substring false positives | medium | Removed `_check_ac_references` entirely; extended structural semantics to honor module docstrings (also resolves BC-023) |
| 017 | Router dead code | medium | Wired `route()` into `process_gate_item`; diagnostics now flow through routing table |
| 018 | MockSubstrate diverges from real substrate | medium | Added `workflow_version` filtering; removed `state_map` fallback; verified `read_events` compatibility |
| 019 | Channel failure modes untested | high | Added `tests/test_channel_failures.py` (5 tests) covering timeout, non-zero exit, empty output, extraction failure, cannot_proceed |
| 020 | Config YAML loading untested | low | Added `tests/test_config.py` (6 tests) covering full YAML load, defaults, `from_yaml_or_default`, role lookup |

**Breadcrumbs raised and resolved (this session):**

| # | Title | Severity | Rationale |
|---|---|---|---|
| 023 | Structural semantics gate rejected module-level AC docstrings | high | Discovered during BC-016 fix; module docstrings now honored |
| 024 | `_resume_and_submit` hardcodes role to `interface_architect` | high | Discovered during BC-014 fix; parameterized `role_name` |
| 022 | Integration tests access substrate private API | medium | `factory_config` fixture introduced using public `substrate.project` closes the immediate coupling |

**Technically still open (deferred to substrate):**
- BC-015 remains open at substrate level (request for `Substrate.dsn` public property). Factory workaround in place via `factory_config` fixture.

**Code changes:**

1. `src/factory/runner.py` — `_resume_and_submit` now accepts `role_name` parameter; `_handle_invoke_failure` now calls `sub.append_event(transition="channel_fail")` with structured diagnostics.
2. `src/factory/gate.py` — Removed `_check_ac_references`; module docstrings now included in `_check_structural_semantics` AC binding.
3. `src/factory/gate_process.py` — Replaced hardcoded transitions with `route()` calls; diagnostics sourced from `Route.custom_fields_update`.
4. `tests/_mock_substrate.py` — `query_work_items` filters on `workflow_version`; `transition` requires loaded workflow; added `append_event` method.
5. `tests/conftest.py` — Added `factory_config` fixture using only public Substrate APIs (`substrate.project`).
6. `tests/test_runner_smoke.py` — Refactored to use `factory_config` fixture.
7. `tests/test_gate_process.py` — Refactored to use `factory_config` fixture; fixed test artifact to use module docstring.
8. New files: `tests/test_runner_resume.py`, `tests/test_channel_failures.py`, `tests/test_config.py`.

**Test count:** 125 pass, 1 skip (adversarial item not found in current project). Up from 111.

**Lint:** Clean (ruff checks pass).

---

## 2026-05-06 — Session 4: Phase 1 exit, 10/10 + cannot_proceed

**Invocation:** OpenCode (opencode)
**Model:** deepseek-v4-pro

**Focus:** Execute Opus's 4-phase golden-run test plan. Phase A pre-flight fixes, Phase B dry run, Phase C full measurement, Phase D post-mortem.

**Result: Phase 1 exit criteria PASS — 10/10 primary locked, adversarial in cannot_proceed, 100% first-attempt pass rate. Semantic spot-checks on items 01/04/07 confirm correctness, not just syntactic validity.**

**Actions taken:**

1. **Phase A — Pre-flight fixes:**
   - Fixed `report.py` adversarial check: now filters `by_shape["adversarial"]` and asserts adversarial items are in `cannot_proceed`, not "any item is."
   - Added `raw_stdout.txt` capture to `claude_code_channel.py` — writes `result.stdout` before extraction.
   - Smoke-tested Claude: single fenced `python` block, no preamble, extraction clean.
   - Set `workspace_root: /tmp/sf2-golden-001` in `golden-run-001-config.yaml`.
   - Created `golden-run-001-log.md`.

2. **Phase B — Dry run on item 01:**
   - Added `--only` flag to `populate_work_items.py`.
   - **B4 discoveries (fixes applied):**
     - Runner missing `claim` transition — `acquire_claim` only creates DB row; added `sub.transition(wi, "claim", ...)` in `worker_loop`.
     - `derive_context()` replaced work-item `spec_section` with factory `spec.md` when `spec_file` was set; fixed to prefer work-item content.
     - `register_actor_role` fails idempotently on restart; wrapped in `try/except`.
     - `populate_work_items.py` stale API (`create_work_item` no longer takes `workflow_version`; returns tuple).
     - PyPI vs local substrate collision; resolved via `uv pip install -e /projects/substrate`.
   - Dry run success: item 01 went new→locked in ~19s wall-clock. Claude produced correct variant-type `.pyi`.

3. **Phase C — Full measurement run:**
   - Populated all 11 items (01-10 + AA).
   - Started factory-run + factory-gate.
   - Run completed in ~3.5 minutes: 10/10 locked, 1/1 adversarial in cannot_proceed.
   - Re-ran a second time after BC-012 workspace cleanup test nuked the first workspace; second run also 10/10.

4. **Phase D — Post-mortem:**
   - Semantic spot-check on 01 (pure-interface), 04 (error-taxonomy), 07 (ADT-validation): all PASS.
   - Adversarial item: Claude emitted single fenced JSON block, no stub alongside — prompt working as designed.
   - 71 tests pass (61 original + 10 structural-equivalence), lint clean.

5. **Breadcrumbs filed (BC-008 through BC-013):**
   - BC-008: Fixture AC-15 mislabel — fixed.
   - BC-009: context_hash→artifact non-determinism — `structural_signature()` + `structurally_equivalent_pyi()` added with 10 tests.
   - BC-010: `--reset` doesn't clean workspace — `--workspace-root` flag added.
   - BC-011: Test gap — claim transition not asserted (open).
   - BC-012: Test gap — spec_file paths not exercised (open).
   - BC-013: Gate is syntactic-only — central Phase 2 design question (open).

6. **Commits:**
   - `276ab5c` — Code remediation (claim transition, context fix, structural equivalence, idempotency).
   - `80447e2` — Fixtures, scripts, run-log, golden-run-001 forensic artifacts.
   - Tagged `phase1-exit` at `80447e2`.

**What remains:**
- BC-011 and BC-012 are open test gaps (non-blocking for Phase 2 start).
- BC-013 is the central Phase 2 design question — semantic gating strategy.
- Phase 2 begins with adding remaining roles one at a time (tests → impl → gates).

---

## 2026-05-06 — Session 3: Phase 1 implementation (Waves 0–6)

**Model:** glm-5.1
**Invocation:** OpenCode

**Focus:** Execute the Phase 1 implementation plan (`plans/phase1-implementation.md`) now that substrate is stable. All six build waves completed.

**Context:** Principal confirmed substrate is ready (BC-021 resolved, BC-027/028/029 all resolved in substrate). Instruction was to proceed through all waves.

**Actions taken:**

1. **Applied §9.12 spec amendment** from BC-003 to `spec.md` — runner idempotency on restart mechanics (content-addressed resumption, quarantine, original actor metadata on resume).

2. **Wave 0 — Repo skeleton:**
   - `pyproject.toml` with substrate dependency, `factory-run` and `factory-gate` entry points, ruff/pytest config.
   - `src/factory/__init__.py` package.
   - `tests/conftest.py` with module-scoped substrate fixture + workspace_root fixture.
   - `tests/test_keys.json` matching substrate's test keys.

3. **Wave 1 — Workspace + manifest** (`src/factory/workspace.py`):
   - `ArtifactManifest` frozen dataclass with sha256, size, actor metadata fields.
   - `attempt_dir()`, `write_artifact()` (atomic temp-then-rename), `find_resumable_artifact()`, `quarantine_attempt()`, `list_attempt_dirs()`.
   - 15 tests in `tests/test_workspace.py` covering round-trip, multi-attempt, tampering, quarantine.

4. **Wave 2 — Channel interface** (`src/factory/channel.py`):
   - `InvocationResult` frozen dataclass, `Channel` protocol (runtime_checkable).
   - `MockChannel` in `tests/_mock_channel.py` with fixture-based artifact replay, `cannot_proceed.json` support, call logging.
   - 7 tests in `tests/test_channel.py`.

5. **Wave 3 — Context derivation + failure summary**:
   - `src/factory/context.py`: `derive_context()` producing `PromptContext` with deterministic `context_hash` (sha256 of sorted JSON bundle). Reads from substrate, spec section, AC IDs, glossary, prior failures, role prompt template.
   - `src/factory/failure_summary.py`: `derive_failures()` extracts `gate_fail` events from substrate event log into structured `FailureEntry` list.
   - 9 tests in `tests/test_context.py` and `tests/test_failure_summary.py` covering determinism, sorted keys, empty/multi-failure cases.

6. **Wave 4 — Gate engine + router**:
   - `src/factory/gate.py`: `evaluate_interface_spec()` with four gates: file exists, not empty, valid Python syntax, valid .pyi stub (no implementation bodies), AC references present. Returns `GateResult` frozen dataclass.
   - `src/factory/router.py`: `route()` function. Phase 1: `gate_pass → locked`, `gate_fail → new` with diagnostics propagation. Structured for Phase 2 expansion.
   - 12 tests in `tests/test_gate_interface_spec.py` and `tests/test_router.py`.

7. **Wave 5 — Runner loop + gate process + config + ClaudeCC channel**:
   - `src/factory/config.py`: `FactoryConfig` frozen dataclass with role bindings, timeouts, workspace root.
   - `src/factory/runner.py`: Worker loop (claim → check resumable → derive context → invoke channel → write artifact → submit). Resume from prior attempt with original actor metadata. Separate `_handle_invoke_failure` for cannot_proceed vs channel error.
   - `src/factory/gate_process.py`: Gate loop (poll gating items → claim → evaluate gates → gate_pass/gate_fail). Separate process from worker per plan.
   - `src/factory/claude_code_channel.py`: `ClaudeCodeChannel` spawning `claude-code --print` headless with timeout, output capture, cannot_proceed detection.
   - 10 tests in `tests/test_runner_smoke.py`, `tests/test_runner_idempotency.py`, `tests/test_gate_process.py` (3 integration tests require live Postgres).

8. **Wave 6 — Golden-run infrastructure**:
   - `tests/fixtures/golden-run-001/README.md` — placeholder for first real Claude CC run.
   - `tests/fixtures/primary-spec/README.md` — 10-item test set partition (3 pure-interface, 3 error-taxonomy, 3 ADT-validation, 1 adversarial) drawn from substrate spec.
   - `tests/test_golden_run.py` — 5 tests: fixture structure validation, manifest round-trip, pending golden-run detection.
   - Secondary spec (`tests/fixtures/secondary-spec/spec.md`) already existed from Opus's session.

**Files delivered:**

```
src/factory/
  __init__.py
  channel.py          # Channel Protocol, InvocationResult
  claude_code_channel.py  # Claude CC headless adapter
  config.py            # FactoryConfig dataclass
  context.py           # derive_context() → PromptContext with context_hash
  failure_summary.py   # derive_failures() from substrate event log
  gate.py              # evaluate_interface_spec() → GateResult
  gate_process.py      # Gate loop entry point (factory-gate CLI)
  prompts/
    interface_architect.md  # Role prompt (from Opus session)
  router.py            # route() — Phase 1 failure routing
  runner.py            # Worker loop entry point (factory-run CLI)
  workspace.py         # Artifact addressing, manifests, quarantine

tests/
  conftest.py          # Substrate + workspace fixtures
  test_keys.json
  _mock_channel.py     # MockChannel test double
  test_channel.py      # 7 tests
  test_context.py      # 6 tests
  test_failure_summary.py  # 3 tests
  test_gate_interface_spec.py  # 8 tests
  test_gate_process.py # 1 integration test
  test_golden_run.py   # 5 tests
  test_router.py       # 4 tests
  test_runner_idempotency.py  # 7 tests
  test_runner_smoke.py # 2 tests (1 integration)
  test_workspace.py    # 15 tests
  fixtures/
    golden-run-001/README.md
    primary-spec/README.md
    secondary-spec/spec.md  # (existed)
```

**Breadcrumb status:**
| # | Title | Severity | Status |
|---|---|---|---|
| 003 | Runner idempotency on restart | high | implemented (spec §9.12 applied, workspace + tests done) |
| 002 | Runner skeleton complexity risk | medium | implemented (7 modules built per BC-002 decomposition) |
| 001 | Dead error codes | low | resolved (prior session) |

**Spec amendment applied:** §9.12 (Runner idempotency on restart) per BC-003.

**59 tests pass** (56 unit + 3 integration against live Postgres). All ruff checks clean.

**What remains for Phase 1 exit:**
- Populate golden-run-001 with real Claude CC execution data.
- Curate and create the 10 primary + 3 secondary + 1 adversarial work-items in substrate.
- Run `factory-run` + `factory-gate` against the curated test set.
- Measure first-attempt pass rate; must exceed 90% on primary set.
- If pass rate is insufficient, iterate on `prompts/interface_architect.md` (max 3 revisions per plan plateau handling).

---

## 2026-05-06 — Session 2: Codebase scan, breadcrumb triage

**Model:** claude-opus-4-7
**Invocation:** Claude Code

**Focus:** Scan repository for inconsistencies; triage BC-001 and raise runner-complexity breadcrumb.

**Context:** Principal asked for a full-repo scan plus specific review of BC-001.

**Findings:**
- **BC-001 is structurally in the wrong repo.** The error codes referenced (`CLAIM_NOT_EXPIRED`, `IDEMPOTENCY_COLLISION`, `LIBRARY_IS_SOLE_SIGNER`, `DEPRECATED_KEY_ID`, `REPLAY_HALTED`, `HOOK_NOT_DEAD_LETTERED`) all belong to substrate's `_errors.py`, not the factory. The two audit artifacts (`audit-error-paths.md`, `audit-spec-alignment.md`) are substrate-level code audits. Keeping them in the factory creates false confidence and splits tracking.
- **Runner complexity is still undesignated.** Spec §8.5 identifies it as the most likely failure mode, but there is no breadcrumb, no design artifact, and no decomposition for the runner skeleton. Phase 1 cannot start without this.
- **Worklog/artifact mismatch:** Session 1 worklog says "breadcrumbs raised: None yet" but three audit files existed in `breadcrumbs/`. Minor inconsistency.

**Actions taken:**
1. **Moved BC-001 to substrate.** Created `substrate/breadcrumbs/026-dead-error-codes.md` (matching substrate's numbering; next after resolved 025). Moved `audit-error-paths.md` and `audit-spec-alignment.md` to `substrate/breadcrumbs/` as attachments.
2. **Resolved BC-001 in factory.** Moved `BC-001-dead-error-codes.md` to `breadcrumbs/resolved/` and updated `breadcrumbs/README.md`.
3. **Raised BC-002 in factory.** Created `breadcrumbs/002-runner-skeleton-complexity.md` with suggested 7-module decomposition, acceptance criteria, and spec references (§4, §5, §8.5, §9).
4. **Updated substrate README.** Added BC-026 to substrate's open breadcrumbs index.

**Breadcrumb status:**
| # | Title | Severity | Status |
|---|---|---|---|
| 002 | Runner skeleton complexity risk | medium | proposed |
| 001 | Dead error codes: defined but never raised | low | resolved (moved to substrate/026) |

**Open questions remaining:**
- Runner decomposition needs principal review (BC-002).
- spec.yaml sidecar deferred to Phase 1 — should have a design note/breadcrumb so it's not an afterthought.

**Test Results:** N/A (no code yet)
**Lint:** N/A

---

## 2026-05-05 — Session 1: Project bootstrap

**Model:** claude-opus-4-7
**Invocation:** Claude Code

**Focus:** Create software-factory-2 project skeleton and initial design spec.

**Context:** Long discussion with the principal about v2 architecture, working from lessons of software-factory v1 (skeleton/test architect failure modes), the constraint that the principal is a systems architect not a developer, and the fleet of model channels available (Claude via CC subscription, Kimi K2 via API, GLM-5.1 via z.ai, DeepSeek V4 via Ollama Pro, Gemini via gemini-cli, OpenCode for non-Anthropic harnessing).

**Delivered:**
- `spec.md` — design spec (10 sections + glossary). Captures purpose, non-goals, principles, pipeline stages, fleet/role binding, failure handling, observability, open questions, and phasing.
- `README.md` — one-paragraph project summary, status, dependencies.
- `AGENTS.md` — agent orientation, conventions, status, what not to build yet.
- `breadcrumbs/README.md` — schema borrowed from substrate, severity/tags defined.
- `.factory/worklog.md` (this file) and `.factory/reflections/` directory.

**Architectural decisions captured:**
- Substrate is the spine; no ad-hoc state in the factory.
- Sequential pipeline; parallelism deferred.
- Autonomy via model-as-expert review (frontier judges replace human gates).
- AC-driven tests are the contract.
- Mechanical gates before LLM gates.
- Filling-in roles, not architectural roles.
- Errors loop back to contract revision before worker retry.
- Jury-and-race for load-bearing gates; subscription cost model rewards aggressive gating.
- Per-role per-channel telemetry drives model placement; no silent promotion.

**Initial role-to-channel binding** documented in spec §5 as configuration, not contract.

**Phasing:** 6 phases, Phase 0 (substrate completion) blocking. v2 cannot start Phase 1 until substrate BC-021 is resolved and Phase 2 stabilizes.

**Breadcrumbs raised:** None yet — Phase 0 design is captured in the spec, not in breadcrumbs.

**Open questions surfaced in spec §8:**
- K2.6 capability impact (~3 days from drafting).
- Long-context degradation in Gemini and DeepSeek (~200-300K threshold).
- Gemini-cli inconsistency (probationary placement).
- Substrate dependencies (BC-021 highest-priority known blocker).
- Runner complexity (likely the most underbudgeted area).
- Semantic AC ambiguity (no structural defense; pushed to spec quality).
- Fleet management overhead (cap at 10% of factory engineering time).
- First-target application domain (TBD; not socratic-spec or software-factory itself).
- Test theater (acknowledged incomplete defense).
- Cost of jury at scale (wall-clock, not dollars).

**Test Results:** N/A (no code yet)
**Lint:** N/A
