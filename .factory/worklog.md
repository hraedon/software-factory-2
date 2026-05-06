# Software Factory v2 — Worklog

Reverse-chronological session log. Prepend new entries above existing ones.

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
