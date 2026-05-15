---
number: "RFC-027"
title: "Test efficacy — no mechanical verification that tests actually validate behavior"
severity: high
status: proposed
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

## What mutation testing would add

Mutation testing (RFC-007) mechanically verifies test efficacy by:
1. Taking the locked implementation.
2. Introducing a small defect (swap `>` for `<`, delete a line, change a constant).
3. Running the test suite against the mutated implementation.
4. If the tests still pass, the tests don't cover that class of defect.

This directly addresses failure modes 1, 2, and 4. It does not address 3 (mock-specific testing) or 5 (collusion), which require model-mediated review.

## Design constraints

- Mutation testing is **slow** — N mutants × test suite runtime. For an 8-module project, this could take hours.
- Mutation testing produces **noise** — some mutations are semantically equivalent despite different syntax. Filtering equivalent mutants is itself a hard problem.
- Mutation testing adds a **new mechanical gate** (the pipeline already has 16 deterministic gates in Phase 5). The gate budget (§10) allows for growth but each gate adds latency.
- The simplest approach is a **spot-check** gate: run mutation on a random subset of modules (not all), fail only if the test suite misses >50% of mutations.

## Phase needed

Phase 6 or later. Mutation testing requires a stable implementation artifact (the .py that passes all existing gates) and a stable test suite. Phase 5 is still validating that integration and outcome verification work at all.
