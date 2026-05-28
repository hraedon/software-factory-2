---
number: "002"
title: "Runner skeleton complexity risk"
severity: medium
status: implemented
kind: design
author: opencode
date: "2026-05-06"
tags: [runner, design, phase-1]
related: []
---

## Problem

The spec (§8.5) identifies "Runner complexity" as the most likely failure mode for v2: "The channel-adapter + telemetry + failure-routing layer is a real engineering investment, not a weekend script. Underbudgeting this is the most likely failure mode for v2."

The `workflows/README.md` confirms that hook implementations, gate code, context derivation, work-item creation/routing, and channel adapter logic are all runner-side. That is a large amount of code that must be designed before Phase 1 starts.

## Current gap

There is no decomposition or design artifact for the runner itself. The spec describes what the runner does (§4, §5, §9), but not how its internal modules are structured. Without this, Phase 1 risks becoming a monolith that is hard to test and harder to debug. In addition, the decomposition in the original write-up was too coarse — it hand-waves the hardest part (the runner loop) and over-engineers the easiest part (config parsing).

## Analysis: what is actually hard

After working through the implications of `phase1.yaml`, `workflows/README.md`, and the spec's memory architecture (§9), here is a revised assessment of complexity by module:

### High-complexity modules (need design before Phase 1 code)

1. **Runner loop / core** — This is NOT "event loop + polling." It is a state-machine executor that:
   - Polls regista for *claimable* work-items matching runner-registered roles (using regista's `acquire_claim` API, not raw polling).
   - On claim: derives context, invokes channel adapter, writes artifact to workspace, transitions work-item via `submit`.
   - On submit: triggers gate evaluation (mechanical_gate claims the work-item, runs gates, transitions to `locked` or `new` via `gate_pass`/`gate_fail`).
   - The key hard part: **the runner must be idempotent across restarts.** The work-item's `artifact_path` + `artifact_hash` custom fields are the audit trail. If the runner crashes after channel invocation but before `submit`, re-claiming the same work-item must either (a) detect the existing artifact and resume, or (b) overwrite and proceed. This is not regista's concern — it is runner concern.

2. **Router / orchestrator** — The `gate_fail` transition in `phase1.yaml` routes back to `new`. In the full pipeline (`full_pipeline.yaml`), routing is more complex: Stage 5 fail → Stage 4, Stage 6 fail → Stage 4 OR Stage 3, Stage 7 jury disagreement → Stage 2, Stage 2 exhausted → principal escalation. This routing table is currently implicit. It must be made explicit and testable.

3. **Failure-summary derivation** — Spec §9.4 requires structured `failures.json` from the event log for retry attempts. This is a *derived artifact* (not stored state). Implementing it correctly before the first retry loop matters, because without it, the second attempt gets no context and fails the same way.

4. **Context derivation** — Spec §9.2 requires *deterministic* context derivation. Two invocations on the same regista state must produce byte-identical prompt bundles. This means the derivation function must be pure (no filesystem reads outside regista, no ambient state), and the test suite must catch non-determinism.

### Medium-complexity modules (can be stubbed, iterate in Phase 1)

5. **Channel adapter interface** — The `Channel` protocol (spec §5) is fine. The complexity is NOT the interface; it is the *harness* for each channel. Claude CC headless is the only Phase 1 channel. The adapter must: spawn CC headless with a project dir, inject the prompt, capture stdout/stderr + exit code, parse the result. This is harness-specific error handling (timeouts, partial writes, CC version drift), not an abstract problem.

6. **Gate engine** — For Phase 1, the mechanical gates for `interface_spec` are: (a) is the artifact a valid `.pyi` file? (b) does it parse with `ast`? (c) does it reference the declared `spec_section` ACs? These are small, deterministic checks. The pluggable-per-type architecture can be deferred.

7. **Telemetry** — Phase 1 only needs *event logging* (which regista does). Per-role per-channel pass-rate aggregation is a Phase 2/3 concern. Do not build the nightly reporter yet.

### Low-complexity modules (do not need dedicated files yet)

8. **Config** — `factory.config.yaml` for Phase 1 is tiny: one channel binding, one role mapping, one timeout. Hot-reloading is not needed until Phase 3. A dataclass loaded at startup is sufficient; a dedicated module is premature.

## Revised decomposition for Phase 1

```
src/factory/
  __init__.py
  runner.py        # Main loop: claim → derive_context → invoke → gate → transition
  context.py       # derive_context(work_item_id, role) -> PromptContext (pure, tested)
  gate.py          # Mechanical gates per work-item type. Phase 1: interface_spec only.
  channel.py        # Channel Protocol + ClaudeCCHeadlessChannel
  router.py         # Failure routing table. Phase 1: gate_fail -> new only.
  workspace.py      # Artifact addressing (§9.11): content-addressed paths, manifest writing
  failure_summary.py    # derive_failures(work_item_id) -> failures.json from event log
  config.py        # Tiny dataclass. Not hot-reloadable in Phase 1.

tests/
  test_context.py        # Determinism: same regista state -> identical bundle
  test_gate_interface_spec.py  # Valid / invalid .pyi artifacts
  test_router.py          # Routing table unit tests
  test_failure_summary.py    # Event log -> structured failures
  test_workspace.py       # Content-addressed paths round-trip
  test_runner_smoke.py   # End-to-end with mock channel (no real CC needed)
```

## Critical changes from original decomposition

1. **Added `workspace.py`** — Content-addressed artifact paths (spec §9.11) are a cross-cutting concern. They touch context derivation (input artifacts), channel invocation (output artifacts), and gate evaluation (reading artifacts). Without a dedicated module, this logic leaks into every other module.

2. **Added `failure_summary.py`** — Spec §9.4 is explicit that this is a derived artifact. It is also the primary way a retry attempt receives context. It deserves its own module and tests.

3. **Merged telemetry into runner** — Phase 1 telemetry is "write actor metadata to regista event log." That's a one-liner at the claim/transition call site. No dedicated module needed until pass-rate aggregation becomes real (Phase 3).

4. **Downgraded config** — A single dataclass is sufficient for Phase 1. A whole module is over-engineering against a problem (hot reloading) that Phase 1 doesn't have.

5. **Renamed `runner/core.py` to `runner.py`** — A single module is sufficient for Phase 1. The loop is not complex enough to split. If it grows beyond ~400 lines in Phase 2, then split into `core.py`, `claim_loop.py`, `transition_loop.py`.

## What's missing and should be decided now

1. **Gate pass vs gate fail criteria** for `interface_spec`. The spec says Stage 5 is "type check, test run, lint, regista replay drift = 0". But `interface_spec` has no tests yet — the test author hasn't run. So Phase 1 gates must be: (a) valid Python syntax, (b) type-checkable, (c) references the declared spec_section. The full gate suite applies to `implementation` work-items (Phase 2).

2. **Hook notification mode** — Resolved: hooks-with-poll-fallback. Regista BC-021 is now resolved. The runner registers async hooks on `gate_pass` and `gate_fail` transitions for downstream stage triggering. If the hook consumer loses its connection and cannot reconnect within the configured backoff window, the runner falls back to polling for `new` work-items in its registered roles. The fallback is **not** a configuration switch — it is hard-coded behavior that every runner instance exhibits when hooks are unavailable. This avoids a test-matrix doubling. See `workflows/README.md` "Hook-driven stage progression" and regista BC-021.

3. **Test strategy for runner** — How do we test the runner without a real Claude CC instance? The answer: a `MockChannel` that reads prompt + input artifacts from a fixture directory and produces a pre-recorded artifact. The runner should be testable end-to-end with this mock. The `MockChannel` is a test double, not production code.

## Acceptance criteria (revised)

- [ ] `src/factory/` directory structure exists with modules listed above.
- [ ] `runner.py` main loop is testable with `MockChannel`; no real model channel needed for unit tests.
- [ ] `tests/test_context.py` proves determinism: same regista state -> byte-identical prompt bundle for at least one role.
- [ ] `tests/test_gate_interface_spec.py` covers happy path (valid .pyi) and three failure modes (syntax error, missing AC reference, invalid type stub).
- [ ] `tests/test_router.py` covers gate_fail -> new routing for Phase 1.
- [ ] `tests/test_failure_summary.py` covers: single failure -> correct failures.json; multiple failures -> all included; no failures -> empty dict.
- [ ] `tests/test_workspace.py` covers content-addressed path generation and manifest hash verification.
- [ ] `config.py` is a dataclass with type hints; no yaml parsing library dependency in Phase 1.
- [ ] `tests/test_runner_idempotency.py` covers crash-before-submit resume, crash-during-write discard, and manifest-tampering discard. (See BC-003 for spec.)

## Related

- spec §4 (Failure routing)
- spec §5 (Fleet & role-to-channel binding)
- spec §9 (Memory and context)
- spec §8.5 (Runner complexity risk)
- `workflows/README.md` (Hook-driven stage progression)
- regista BC-021 (Hook consumer no reconnect — determines runner notification mode)

## Lessons from v1 software-factory (`/projects/software-factory`)

A review of the v1 codebase reveals patterns worth imitating, things to explicitly discard because regista or the spec makes them unnecessary, and several categories of v1 value (prompts, gate implementations, failure taxonomies) that this first-pass survey did not cover and that should be revisited before Phase 2.

**A note on the word "salvage" below.** Earlier drafts of this section talked about "salvageable subsystems" as if v1 code could be lifted into v2 with light editing. That framing was wrong. v1's `recorder.py` (603 lines) + `replay.py` (706 lines) and `gate_runner.py` (457 lines) are not lift-and-edit targets — the v2 equivalents are an order of magnitude smaller and structurally different. What is being salvaged is *the shape of the idea*, not the code. The entries below are best read as "patterns to imitate," not "modules to port."

### Pattern to imitate: Golden-run / replay (`factory/stages/recorder.py` + `replay.py`)

v1 captures stage I/O, git state, budget, and optionally agent transcripts at checkpoints, then replays them for regression testing. This is exactly what v2 needs for end-to-end runner testing without real model channels.

**Adaptation:** Do NOT port the `PipelineRecorder` class as a separate subsystem. The 1,300 lines of v1 recorder/replay are *not* the right starting point — they capture a much richer state model than v2 needs. In v2, the **workspace manifest** (spec §9.11) IS the recording. The `MockChannel` test double is populated from a golden-run manifest, not from ad-hoc JSON files. Expect to write this fresh against the manifest format, referencing v1 only for "what kinds of state did the v1 author find they needed to capture, and which of those does regista already give us for free?"

How it works in v2:
1. A real Claude CC run produces artifacts + a `manifest.json` (sha256s, paths, role, channel, attempt_id).
2. A test copies the manifest + artifacts into a fixture directory.
3. `MockChannel` (the test double) reads the fixture: given a work_item_id and role, it returns the pre-recorded artifact from the fixture.
4. A `MockSubstrate` test double provides the regista state that the original run produced.
5. The v2 runner test asserts: running the loop with `MockChannel` + `MockSubstrate` produces the same transitions as the original run.

The v1 `FixitTester` concept (test a fix agent on a previously failed FR with mocked LLM responses) maps directly to v2: test the retry loop by having `MockChannel` return a failure on attempt 1 and a corrected artifact on attempt 2.

### Worth adapting: Determinism hashing (`factory/checkpoints.py` `CheckpointInputs`)

v1 checkpoints record `prompt_template_id`, `prompt_template_hash`, `rendered_prompt_path`, `context_hash`, and `spec_hash`. This pattern is directly applicable to v2 spec §9.2 (deterministic context derivation).

**Adaptation:** `derive_context(work_item_id, role)` should compute and return a `context_hash` (sha256 of the serialized prompt bundle). This hash is stored in the regista event log as actor metadata. Tests assert that the same regista state always produces the same `context_hash`. If a refactor changes the prompt bundle for the same state, the hash changes and the golden-run test fails — which is the desired signal.

### Pattern to imitate: Gate result dataclass (`factory/stages/gate_runner.py` `GateRunnerResult`)

v1's `GateRunnerResult` is a structured pass/fail object with per-gate booleans and error messages. v2's gate engine should return a similar structured result that the router consumes.

**Adaptation:** A simpler version (~10 lines, vs v1's 457-line `gate_runner.py`):
```python
@dataclass
class GateResult:
    passed: bool
    gate_name: str  # e.g., "interface_spec_syntax"
    diagnostics: List[str]  # typed error messages for failure routing
    artifact_valid: bool  # does the artifact on disk pass?
```
The router reads `GateResult.diagnostics` to decide whether to route to implementation retry, test revision, or interface revision (spec §4 failure routing table). What's being borrowed from v1 here is "structured per-gate result with typed diagnostics is the right shape for a routing layer to consume" — not the v1 implementation, which carried much more state than v2 routing needs.

### NOT worth adapting: Checkpoint system (`factory/checkpoints.py`)

v1's checkpoint system is sophisticated (git tree hashes, preserved/resettable state, surgical redo, budget state). v2 should NOT port this. Regista's work-item lifecycle (`new → in_progress → gating → locked`) IS the checkpoint system. A "checkpoint" in v1 is a regista work-item state + its event log in v2.

### NOT worth adapting: A-MEM knowledge graph (`factory/memory_graph/`)

v1 implements a 4-tier memory graph (working, episodic, semantic, procedural) on SQLite. v2 spec §9.7 explicitly rejects parallel knowledge stores: "Never free-floating mutable knowledge that workers can read and write." Do not port.

### NOT worth adapting: Agent launcher / worktree isolation (`factory/agents/launcher.py`, `factory/agents/worktree.py`)

v1 manages git worktrees for each agent to provide filesystem isolation. v2's isolation is the channel adapter's concern. Claude CC headless runs in its own project directory; K2 API is stateless. The worktree machinery is unnecessary complexity.

### NOT worth adapting: Budget circuit breaker (`factory/utils/budget.py`)

v1 has per-run token tracking with CLOSED/OPEN/HALF_OPEN circuit breaker states. v2's cost model is subscription-flat-rate (spec §5). The only "budget" is a per-role wall-clock timeout in the config. No circuit breaker needed.

### NOT worth adapting: Telemetry module (`factory/telemetry.py`)

v1's telemetry is a compat shim (moved to `factory.audit.telemetry`) that collected its own metrics. v2 telemetry is regista event log queries. The nightly pass-rate reporter is a small script that runs SQL against regista's event store, not a module.

### What this first-pass survey missed

The discard/salvage analysis above looked at v1's *code architecture*. It deliberately skipped the categories where v1 actually banked judgment that's worth porting. These need a second-pass survey before Phase 2 starts adding roles beyond `interface_architect`.

1. **Prompt corpus and role definitions.** `factory/stages/` contains ~50 modules including `interface_review`, `test_architect`, `stubs`, `wiring_agent`, `merge_review_gate`, `failure_loop`, `adversarial_security`, `mutation_testing`, etc. Many of these encode role-prompt content, system-prompt structure, and prompt-engineering choices that map directly to v2 roles (`interface_architect`, `test_author`, `implementer`, `cross_family_reviewer`). For an autonomous factory, the prompt corpus is arguably the more valuable salvage target than any module of code. Phase 2 should start with a prompt-by-prompt review before authoring v2 role prompts from scratch.

2. **Mechanical-gate implementations.** v1 has `validation/`, `validation_gates/`, `local_validator.py`, `endpoint_validation.py`, `clean_install_validation.py`, `import_check.py`, `static_analysis/`, `mutation_testing.py`. v2 spec §4 lists Stage 5 as "type check, test run, lint, replay drift = 0" — substantially thinner than what v1 actually built. Phase 1's gate set (syntax, AST, AC reference) is correctly minimal, but **v1's gate library is a Phase 2 salvage target, not a permanent discard.** The "interesting" gates v1 evolved (mutation testing, endpoint validation, clean-install validation) encode real lessons about what catches regressions in autonomous pipelines.

3. **Failure-routing taxonomies.** `escalation.py`, `failure_loop.py`, `retry_utils.py` likely encode hard-won judgment about how to *classify* failures and decide where they route. v2's spec §4 routing table and BC-002's `router.py` need to make these decisions explicitly. Before finalizing the Phase 1 routing table, review v1's failure taxonomies — even if the code does not port, the *categories* (recoverable-by-retry, recoverable-by-contract-revision, structural-ambiguity, dead-letter-worthy) should inform v2's routing diagnostics.

4. **Spec evolution.** v1 has `spec_elicitation.py` and `spec_evolution.py`. v2 outsources Stage 0 (initial elaboration) to socratic-specification, but Stage 10 → "feedback as new/revised AC, re-run affected stages" is in scope for v2 and is *not* socratic-specification's job. v1's spec-evolution module is the closest existing prior art for "the principal updates an AC; what stages need to invalidate and re-run?" — review before designing Stage 10's revision flow.

These four are not blockers for Phase 1 (single-role end-to-end on `interface_architect`) but should be opened as their own breadcrumbs before Phase 2 expands the role set.

### Summary of adaptation mapping

| v1 Component | v2 Equivalent | Verdict |
|---|---|---|
| `recorder.py` + `replay.py` | Workspace manifest + `MockChannel` fixture | **Imitate pattern** — write fresh against manifest format; do not port the 1,300 lines |
| `CheckpointInputs` hash records | `derive_context` context_hash | **Imitate pattern** — small, genuinely portable |
| `GateRunnerResult` | `GateResult` dataclass | **Imitate pattern** — borrow the shape, write a ~10-line dataclass |
| Prompts in `factory/stages/*` | v2 role system prompts (spec §9.6) | **Phase 2 review** — survey prompt-by-prompt before authoring v2 roles |
| `validation/`, `validation_gates/`, `mutation_testing.py`, `static_analysis/` | v2 mechanical gates (Stage 5) | **Phase 2 review** — Phase 1 is minimal; Phase 2 should mine v1's gate library |
| `escalation.py`, `failure_loop.py`, `retry_utils.py` | v2 router + spec §4 routing table | **Phase 2 review** — port the failure *taxonomies*, not the code |
| `spec_elicitation.py`, `spec_evolution.py` | socratic-specification (Stage 0) + v2 Stage 10 revision flow | **Phase 2 review** — closest prior art for AC-revision invalidation |
| `checkpoints.py` (full system) | Regista work-item lifecycle | **Discard** — regista replaces it |
| `memory_graph/` | Nothing (spec §9.7) | **Discard** — explicit anti-pattern in v2 |
| `agents/launcher.py` + `worktree.py` | Channel adapter | **Discard** — adapter handles isolation |
| `utils/budget.py` circuit breaker | Per-role timeout in config | **Discard** — subscription model removes need |
| `telemetry.py` | Actor-metadata population in runner transition wrappers + regista event log SQL queries | **Discard** — regista is the source of truth |

### New acceptance criteria from v1 lessons

- [ ] `tests/fixtures/golden-run-001/` contains a real run's manifest + artifacts + regista state snapshot.
- [ ] `MockChannel` can be initialized from a fixture directory and replays the run deterministically.
- [ ] `derive_context` returns a `context_hash`; golden-run test asserts hash matches recorded hash.
- [ ] A golden-run test runs the full `runner.py` loop with `MockChannel` + `MockSubstrate` and produces the same sequence of transitions as the original run (verified by comparing emitted regista events).
