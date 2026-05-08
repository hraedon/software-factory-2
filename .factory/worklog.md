# Software Factory v2 — Worklog

Reverse-chronological session log. Prepend new entries above existing ones.

---

## 2026-05-08 — Session 13: Fix BC-041 — _create_channel factory crash on default config

**Invocation:** Claude Code

**Focus:** Fix a startup-crash bug discovered while reviewing BC-040 implementation.

**Bug:** `runner.py:_create_channel()` iterated over `config.roles` to build a set of distinct channel names. The default config includes `mechanical_gate` with `channel="code"` (deterministic evaluation, not a model channel), producing a set of size 2 (`{"claude-code", "code"}`). This unconditionally raised `NotImplementedError("Multi-channel dispatch not yet implemented")`, crashing `python -m factory.runner` with no config.

**Fix:** Filter out `channel="code"` before the set cardinality check:
```python
channels = set(rc.channel for rc in config.roles if rc.channel != "code")
```

**Tests:** Added `TestCreateChannel` in `tests/test_runner_coverage.py` with 4 cases:
1. Default config → `claude-code` (was failing before fix)
2. Phase 1 config → `claude-code`
3. Phase 2 opencode config → `opencode`
4. Multi-model config (`claude-code` + `opencode`) → raises `NotImplementedError`

**Result:** 259 passed, 1 skipped, 0 failed.

**Breadcrumb moved to resolved:** `breadcrumbs/resolved/041-create-channel-factory-counts-deterministic-channel.md`

---

## 2026-05-08 — Session 12: Implement BC-039 and BC-040

**Invocation:** Claude Code

**Focus:** Resolve two open breadcrumbs:
- BC-039: Lint gate auto-format + implementer prompt modern typing conventions
- BC-040: OpenCodeChannel adapter with per-role model selection

**Changes:**

1. `src/factory/gate.py` — `_run_ruff()` now runs `ruff check --fix` and `ruff format` before the final `ruff check`. Auto-fixes I001, UP006, UP035, UP045; only unfixable issues (e.g., bare `except`) produce gate_fail.

2. `src/factory/prompts/implementer.md` — Added **Typing conventions** section:
   - Use `X | Y` for unions, `X | None` for optionals; never `Union`, `Optional`
   - Use built-in generics `dict`, `list`, `set`, `tuple`; never `typing.Dict`, etc.
   - Import from `collections.abc` instead of `typing`
   - Import grouping rule

3. `src/factory/runner.py` — Added `_has_prior_gate_fail()` helper; `process_work_item()` now skips resumable-artifact logic when the work-item has prior `gate_fail` or `channel_fail` events. This prevents resubmitting a gate-rejected artifact.

4. `src/factory/output_extraction.py` — New shared module extracted from `claude_code_channel.py`. Contains model-agnostic `extract_artifact_from_output()` and `extract_json_from_output()`.

5. `src/factory/claude_code_channel.py` — Imports from `output_extraction.py`; re-exports private names for backward compatibility with existing tests.

6. `src/factory/opencode_channel.py` — New `OpenCodeChannel` implementing the `Channel` protocol:
   - Invokes `opencode run --dangerously-skip-permissions --model <provider/model>`
   - Per-role `model` selection via `RoleConfig.model`
   - Family derived from model provider prefix (`zai-coding-plan/*` → `zai`, `ollama-cloud/*` → `ollama`, etc.)
   - Same error handling pattern as `ClaudeCodeChannel`

7. `src/factory/runner.py` — Added `_create_channel()` factory replacing hardcoded `ClaudeCodeChannel` import in `main()`. Supports `opencode` and `claude-code` single-channel configs; raises `NotImplementedError` for multi-channel.

8. `tests/test_opencode_channel.py` — New test file: family derivation, artifact extension, channel properties.

9. `tests/test_pipeline_integration.py` — Updated `_BadImplIntegrationChannel` to produce a bare `except` (unfixable by ruff auto-format) so the escalation test still exercises repeated gate failures after the auto-format change.

**Test results:** 255 passed, 1 skipped, 0 failed.

**Breadcrumbs moved to resolved:**
- `breadcrumbs/resolved/039-lint-autofix-and-prompt-modern-typing.md`
- `breadcrumbs/resolved/040-opencode-channel-adapter.md`

---

## 2026-05-08 — Session 10: Wave 7 attempt — golden-run-002 FAILED, module resolution bug found and fixed, escalation no-op discovered

**Invocation:** OpenCode (glm-5.1)

**Focus:** Execute Wave 7 of Phase 2 implementation plan — golden-run-002 with real Claude CC across the full 3-stage pipeline (interface_spec → test_suite → implementation).

**Result: Golden run FAILED. 15/15 interface_specs locked, 15/15 test_suites locked, 0/15 implementations locked. 238/238 unit tests pass, lint clean.**

**Primary failure: Cross-work-item module resolution in subprocess gates.**

The implementation gate's `_run_pytest` and `_run_mypy` could not resolve imports from the `interface` module because the interface `.pyi`, test suite `.py`, and implementation `.py` artifacts lived in separate work-item directories. Test suites import `from interface import ...` (the canonical module name for the locked interface contract), but the implementation file was named `artifact.py` and wasn't on any Python import path. Every implementation attempt failed with `ImportError` on pytest collection.

**Fix applied:** Both `_run_pytest` and `_run_mypy` now create isolated temp directories with correct module names:
- Implementation copied as both its original filename and `interface.py` (for pytest)
- Interface `.pyi` copied alongside as `interface.pyi` (for mypy)
- Test suite copied alongside

**Secondary discovery: Escalation routing is a no-op (BC-037).**

When the router escalates an implementation item after exceeding `attempt_threshold`, it produces `cannot_proceed_seam` diagnostics targeting `interface_architect`. But the item goes back to state `new`, and the worker's `type_to_role` mapping always sends implementation items to the `implementer` role. The implementer re-claims and produces another failing artifact. Items cycled up to 80 times after escalation fired. BC-037 filed.

**Infrastructure changes:**

1. `ClaudeCodeChannel` — `_artifact_extension_for_role()` method: writes `.pyi` for `interface_architect`, `.py` for `test_author`/`implementer`.

2. `KimiAPIChannel` stub — `_artifact_extension_for_role()` added for symmetry.

3. `scheduler.py` — `interface_ref` now passed into `implementation` work items so the gate can resolve the `.pyi` stub.

4. `gate.py` — `_run_mypy` and `_run_pytest` create tempdirs with module aliases.

5. `router.py` — Fixed route map to send implementation failures to implementer, not test_author.

**Breadcrumbs closed:**
- BC-034: Cannot_proceed without diagnostics file causes double-release
- BC-035: InMemorySubstrate get_work_item rejects string UUIDs
- BC-036: InMemorySubstrate claim attempt_number resets after transition

---

## 2026-05-08 — Session 9: Wave 6 — golden-run-001 with 15 real Claude CC interface_spec items

**Invocation:** OpenCode (glm-5.1)

**Focus:** Run first golden run with real Claude CC headless against 15 curated specs, validate end-to-end pipeline with real substrate and real model.

**Result: 12/15 interface_specs locked, 3 escalated. 235/235 unit tests pass.**

**Failures:**
1. Concurrent claim test — interface spec declared a `concurrent_safe` flag but implementation gate's `_run_pytest` had no concurrency harness. Real bug; not a pipeline bug.
2. Adversarial item with deliberately broken syntax — correctly escalated to principal.
3. Ambiguous AC-07 / AC-08 overlap — interface spec vacuous; correctly escalated.

**Telemetry captured:** Per-event actor metadata with role/channel/family/attempt_n working end-to-end.

**New breadcrumbs filed:**
- BC-038: test_suite gate doesn't verify pytest collectability
- BC-039: Implementation lint gate should auto-format before checking
- BC-040: OpenCodeChannel adapter

---

## 2026-05-07 — Session 8: Wave 5 — cross-stage escalation routing

**Invocation:** Claude Code (Sonnet 4)

**Focus:** Build cross-stage escalation (BC-027) so repeated gate failures on a downstream role route back to the upstream contract.

**Changes:**

1. `src/factory/router.py` — `route()` function with `attempt_threshold`. After `attempt_n >= threshold`, gate failures transition to `cannot_proceed` (terminal) with `cannot_proceed_seam` diagnostics.

2. `src/factory/gate_process.py` — `process_gate_item()` now calls `route()` after evaluation.

3. `tests/test_router.py` — Phase 1 routing tests (gate_pass → locked, gate_fail → new).

4. `tests/test_router_phase2.py` — Phase 2 escalation tests:
   - impl_mypy / impl_pytest / impl_lint / impl_import → implementer below threshold
   - Same kinds → interface_architect at/above threshold
   - test_collect / test_import_forbidden → test_author below threshold
   - Same kinds → interface_architect at/above threshold
   - interface_spec failures never escalate (no upstream)

5. `workflows/phase2.yaml` — Added `gate_escalation` transition from `gating` to `cannot_proceed`.

**Test results:** 234 pass, 1 skip.

**Breadcrumbs closed:** BC-027

---

## 2026-05-07 — Session 7: Wave 4 — gate process + scheduler handoffs

**Invocation:** OpenCode (glm-5.1)

**Focus:** Mechanical gate process and scheduler idempotency.

**Changes:**

1. `src/factory/gate_process.py` — Full gate loop + `process_gate_item()` with per-type evaluation.

2. `src/factory/scheduler.py` — `_ensure_downstream_item()` with idempotency checks and per-source `custom_fields` ref validation.

3. `tests/test_scheduler_idempotency.py` — Duplicate handoff, second source, interface ref propagation.

4. `tests/test_gate_process.py` — Integration tests for gate pass / fail / missing artifact.

**Test results:** 224 pass, 1 skip.

**Breadcrumbs closed:**
- BC-025: evaluate_implementation missing subprocess gates
- BC-026: Scheduler idempotency

---

## 2026-05-07 — Session 6: Wave 3 — context derivation + prompt rendering

**Invocation:** Claude Code (Sonnet 4)

**Focus:** Build deterministic context derivation and prompt rendering for interface_architect, test_author, implementer.

**Changes:**

1. `src/factory/context.py` — `derive_context()`, `derive_test_author_context()`, `derive_implementer_context()`, `render_prompt()`.

2. `src/factory/prompts/` — Role-specific markdown templates:
   - `interface_architect.md` — produce locked `.pyi`
   - `test_author.md` — produce tests from AC + interface
   - `implementer.md` — produce implementation from interface + tests

3. `tests/test_context.py` — Determinism, hash differentiation, spec source priority, prompt inclusion.

4. `tests/test_failure_summary.py` — `derive_failures()` and `failures_to_json()` for structured prior-failure summaries.

**Test results:** 206 pass, 1 skip.

**Breadcrumbs closed:**
- BC-012: Context derivation tests should exercise both spec_file paths
- BC-014: Resume path untested at integration level

---

## 2026-05-06 — Session 5: Wave 2 — runner + workspace + channel adapter

**Invocation:** OpenCode (glm-5.1)

**Focus:** Build runner worker loop, workspace artifact management, and Claude Code channel adapter.

**Changes:**

1. `src/factory/runner.py` — `worker_loop()`, `process_work_item()`, failure handling, resume logic.

2. `src/factory/workspace.py` — `write_artifact()`, `find_resumable_artifact()`, `quarantine_attempt()`, SHA-256 manifest.

3. `src/factory/claude_code_channel.py` — `ClaudeCodeChannel` with `_extract_artifact_from_output()` and `_extract_json_from_output()`.

4. `tests/test_runner_smoke.py` — Full loop with mock channel.

5. `tests/test_runner_idempotency.py` — Resume after crash, manifest tampering, multi-crash.

6. `tests/test_runner_resume.py` — `_resume_and_submit()` integration tests.

7. `tests/test_workspace.py` — Round-trip, overwrite safety, resumable search, quarantine.

8. `tests/test_channel_failures.py` — Timeout, non-zero exit, empty output, extraction failure.

**Test results:** 175 pass, 1 skip.

**Breadcrumbs closed:**
- BC-006: MockSubstrate needed for CI-portable tests
- BC-007: Integration tests are stubs
- BC-011: Test gap — claim transition not asserted
- BC-019: Channel failure modes untested
- BC-020: Config YAML loading untested
- BC-021: Non-cannot_proceed channel failures produce no substrate event
- BC-024: _resume_and_submit hardcodes role

---

## 2026-05-06 — Session 4: Wave 1 — config + gate skeleton

**Invocation:** Claude Code (Sonnet 4)

**Focus:** Build config loader and mechanical gate skeleton.

**Changes:**

1. `src/factory/config.py` — `FactoryConfig` dataclass with `from_yaml()`, `from_yaml_or_default()`, `get_role_config()`.

2. `src/factory/gate.py` — `evaluate_interface_spec()`, `evaluate_test_suite()`, `evaluate_implementation()` with syntax, stub, structural-semantic, import, mypy, pytest, ruff gates.

3. `tests/test_config.py` — YAML round-trip, malformed handling, role lookup.

4. `tests/test_gate_interface_spec.py` — Happy path, syntax error, stub check, AC reference, structural semantics.

5. `tests/test_gate_test_suite.py` — File exists, empty, syntax, forbidden import, collect-only.

6. `tests/test_gate_implementation.py` — Happy path, file not found, empty, syntax.

7. `tests/test_gate_implementation_subprocess.py` — Import gate, ruff gate, pytest gate, gate order.

8. `workflows/phase1.yaml` — Single-role workflow (interface_spec → gating → locked).

9. `workflows/phase2.yaml` — Three-role workflow with handoff transitions.

**Test results:** 128 pass, 1 skip.

**Breadcrumbs closed:**
- BC-002: Runner skeleton complexity risk
- BC-003: Runner idempotency on restart
- BC-004: cannot_proceed routing has no workflow path
- BC-005: Spec content resolution
- BC-008: Fixture AC-15 mislabel
- BC-009: context_hash → artifact non-determinism
- BC-010: populate_work_items.py --reset does not clean workspace
- BC-013: Gate is syntactic-only
- BC-015: Integration test private substrate API coupling
- BC-016: AC reference check uses substring search
- BC-017: Router is dead code
- BC-018: MockSubstrate diverges from real substrate
- BC-022: Integration tests access substrate private API
- BC-023: Structural semantics gate rejected module-level AC docstrings

---

## 2026-05-06 — Session 3: Repository setup + spec read

**Invocation:** OpenCode (glm-5.1)

**Focus:** Read spec, scan existing codebase, understand current state.

**Observations:**

- Phase 0 design repo; no runner code yet.
- spec.md is authoritative.
- substrate dependency is real; Phase 1 blocked on BC-021.
- breadcrumbs directory exists with 12 open items (BC-001 through BC-012).

**No code changes.**

---

## 2026-05-05 — Session 2: Design review

**Invocation:** Claude Code (Sonnet 4)

**Focus:** Review spec.md with principal; validate phasing decisions.

**Key decisions:**
- Phase 1 will use Claude CC headless only.
- Phase 3 adds fleet; Phase 4 adds jury/race.
- Do not skip phasing; the v1 lesson is real.

**No code changes.**

---

## 2026-05-05 — Session 1: Kickoff

**Invocation:** OpenCode (glm-5.1)

**Focus:** Initialize repo, write spec.md, write AGENTS.md.

**Files created:**
- `spec.md` — authoritative design spec
- `AGENTS.md` — agent conventions and pointers
- `breadcrumbs/README.md` — breadcrumb schema and index
- `.factory/worklog.md` — this file

**No tests yet.**

---
