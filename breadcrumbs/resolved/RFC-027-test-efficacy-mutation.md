---
number: "RFC-027"
title: "Test efficacy — no mechanical verification that tests actually validate behavior"
severity: high
status: implemented
kind: design
author: agent
date: "2026-05-15"
tags: [rfc, stage-3, stage-6, testing, test-theater]
related: ["RFC-007"]
---

## Summary

The pipeline's quality claim rests on a chain: ACs → tests → implementation → gates → review → jury. But there is no mechanical verification that the tests *actually test the stated behavior*. The existing gates check:
- Tests collect (no import errors)
- Tests pass (no failures)
- Tests have assertions (not empty)
- Tests reference AC IDs (binding check)
- Cross-family review checks for test theater (model-mediated)

None of these confirm that a passing test suite would catch a defective implementation. The cross_family_reviewer is the only defense against test theater, and its effectiveness depends on the reviewer model's judgment — which, as GR-027 showed, can disagree with the jury.

This is the same gap v1 identified (BC-107, BC-186) and is tracked as RFC-007 (mutation testing). But RFC-007 is deferred to Phase 4–5 and has never been prioritized. Meanwhile, GR-027 had 5 test_suite items requiring inner gate retries, and GR-029 had test_author items failing `pytest --collect-only` on first attempt — suggesting test quality is still a bottleneck.

## Concrete failure modes without test efficacy verification

1. **Tautological tests** — test that asserts `result == compute(input)` where `compute` is the function under test. Passes trivially.
2. **No-op tests** — test that calls but never asserts. Caught by assertion-count gate, but assertion count doesn't verify the assertion is meaningful.
3. **Mock-dependent tests** — test mocks the dependency so thoroughly that it tests the mock, not the real code. The cross_family_reviewer is the only defense.
4. **Exception-avoiding tests** — test exercises only the happy path, never the error codes the interface declares. Caught by AC coverage check (if each AC maps to error cases), but only if the AC explicitly enumerates errors.
5. **Test-theater-by-accretion** — after N retries, the test suite "passes" because the implementer wrote code that matches the test's specific assertions, but the assertions don't match the AC.

## Fix

### Mutator integration

RFC-027 is implemented via the existing `mutation_gate.py` module, maintained since Session 51, and wired into the implementation gate path in Session 56. An adversarial review (Opus, 2026-05-29) identified three gaps; all were fixed in the same session.

**1. Configuration (`config.py`):**
- `GateTimeouts.mutation_timeout` — timeout for each mutant test run.
- `OpsConfig.mutation_gate_enabled` — default False, so existing configs are unaffected.
- `OpsConfig.mutation_gate_sample_size` — mutants to evaluate (default 3).
- `OpsConfig.mutation_gate_fail_threshold` — live-mutant tolerance (default 0.5, i.e. 50%).
- `OpsConfig.mutation_gate_seed` — optional RNG seed for reproducibility.
- `FactoryConfig.validate()` checks `sample_size >= 1` and `fail_threshold in [0, 1]`.

**2. Gate wiring (`gate/implementation.py`):**
- `evaluate_implementation` accepts `mutation_enabled`, `mutation_sample_size`, `mutation_fail_threshold`, and `mutation_seed`.
- After the existing pytest gate passes, if `mutation_enabled` is True and `test_suite_path` is provided, it calls `evaluate_mutation_spot_check` from `mutation_gate.py`.
- A failed mutation gate returns its result upstream, aborting the gate sequence early and preserving the same short-circuit behavior as other gates.

**3. Dispatch wiring (`gate_process.py`):**
- `process_gate_item` passes `config.ops.mutation_gate_*` fields into `evaluate_implementation`.
- The mutation gate runs in the mechanical gate process with the same Python executable (gate venv) as mypy/pytest.

**4. Routing (`router.py`):**
- `DiagnosticKind.MUTATION_UNCAUGHT` added to `DiagnosticKind` enum.
- Added to `KIND_DISPATCH` routing table with `target_state=STATE_NEW` and **upstream revision to `test_suite`** (the test author)
- Added to `ESCALATABLE_KINDS` set.

**5. Mutator operator expansion (`mutation_gate.py`):**
- Opus identified the original operator set (comparison swap, constant ±1, return-deletion) as too thin for cert-watch validation.
- Added 3 operators: `BoolOp` swap (`and ↔ or`), `not` removal (`UnaryOp` identity replacement), return-value replacement (`True ↔ False`, non-bool → `None`).
- Arithmetic-operator swaps and string mutations intentionally omitted (high equivalent-mutant rate, low fixture yield per Opus).

**6. Dead-code cleanup (`mutation_gate.py`):**
- Removed unreachable `GATE_NAME_INNER_MYPY` filter branch in `evaluate_mutation_spot_check`.
- Clarified via inline comment and docstring that `_run_suite_on_mutant` runs pytest only, so skipped mutants are purely syntax/import failures.

**7. Telemetry (`telemetry.py`):**
- `GATE_NAME_MUTATION_SPOT_CHECK` already in `DETERMINISTIC_GATES` since Session 52.
- Telemetry correctly counts mutation spot check in deterministic gate metrics.

**8. Tooling parity (`constants.py`):**
- `MUTATION_UNCAUGHT` in `DiagnosticKind`.

**9. Tests:**
- 6 new mutator shape tests in `test_mutation_gate.py` covering BoolOp, UnaryOp, and return-value replacement.
- 4 integration tests in `test_gate_implementation.py` covering disabled skip, enabled strict-pass, enabled lax-fail, and mypy-skip interaction.
- 3 new config validation tests in `test_config.py`.
- Full suite: 1118 passed, 13 skipped, 0 lint, 0 dead code.

### Why this isn't the previous fix recurring

RFC-007 was never fixed — it was a design proposal with no code. The `mutation_gate.py` module (built in Session 51) existed in library form but was not wired into the pipeline. The RFC-027 fix is:

- **It adds the pipeline wiring** that RFC-007 deferred, not a duplicate of a prior wiring.
- **It uses the same `mutation_gate.py`** that Session 51 validated in isolation, but now invokes it deterministically inside the mechanical gate flow rather than as a standalone exercise.

## Design constraints

- Mutation testing is **slow** — N mutants × test suite runtime. For an 8-module project, this could take hours.
- Mutation testing produces **noise** — some mutations are semantically equivalent despite different syntax. Filtering equivalent mutants is itself a hard problem.
- Mutation testing adds a **new mechanical gate** (the pipeline already has 16 deterministic gates in Phase 5). The gate budget (§10) allows for growth but each gate adds latency.
- The simplest approach is a **spot-check** gate: run mutation on a random subset of modules (not all), fail only if the test suite misses >50% of mutations.

## Calibration note

The default `fail_threshold=0.50` is deliberately permissive for Phase 6.2. A golden run with `mutation_enabled=True` should be executed before tightening. If empirical data shows strict test suites commonly kill 80%+ of mutants, the threshold can be raised. The opposite — a high false-rejection rate — would indicate the mutator operator set generates too many semantic-equivalent mutants and needs narrowing.

## Phase needed

Phase 6.2 (generalization). Mutation testing requires a stable implementation artifact (the .py that passes all existing gates) and a stable test suite. Phase 5 is still validating that integration and outcome verification work at all.
