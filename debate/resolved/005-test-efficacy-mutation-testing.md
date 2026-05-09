---
number: "005"
title: "Test efficacy / mutation testing — mechanical antidote to test theater"
author: opencode
date: "2026-05-09"
related: ["RFC-007", "BC-038", "BC-039"]
---

## Context

Spec §8.9 acknowledges **test theater** as an open risk: *"subtle tautologies will get through"* even with a frontier-judge gate checking "do these tests demonstrate AC is met?" The current mitigations are:
- Outcome verification (Stage 9)
- Principal's outcome review (Stage 10)

Neither is automatic or mechanical. Factory's experience (Luke / Factory talk) confirms this: *"Tests written after implementation don't catch bugs. They confirm decisions."*

v1 addressed this with AST-based mutation testing (Bite Score, BC-107/186). v2 has no equivalent.

## Problem

The three-role pipeline's correctness guarantee depends on "tests are the contract." If the contract is vacuous (tautological tests that always pass), the implementer can produce any code and the mechanical gates will green-light it. The frontier judge is supposed to catch this, but:
- It is expensive (multi-model)
- It is not deterministic
- It may itself miss tautologies (especially if the model that wrote the tests also reviews them)

A mechanical mutation-testing gate is cheap, deterministic, and catches the exact failure mode §8.9 worries about.

## Position

**Add a lightweight mutation-testing gate that runs after a test suite + implementation pair passes mechanical gates, before the frontier judge.**

### Minimal implementation

A custom mutator (no heavy dependencies like `mutmut` or `cosmic-ray`) that applies ~10 AST-driven mutation operators:
- Replace `==` with `!=`
- Replace `>` with `<`
- Replace `+` with `-`
- Delete early-return guard clauses
- Swap branch bodies in `if/else`
- Replace `and` with `or`
- Replace `True` with `False` (and vice versa) in boolean contexts
- Replace `0` with `1`, `""` with `"x"` for string defaults

For each mutant:
1. Apply mutation to implementation AST
2. Write mutated code to temp file
3. Run locked test suite against mutant
4. "Killed" = at least one test fails

Compute `kill_rate = killed / total_mutants`. Gate passes if `kill_rate >= threshold` (suggest 0.60 initially, calibrated empirically).

### Why before the frontier judge

Same ordering principle as other mechanical gates: run cheap, deterministic checks before expensive, probabilistic ones. The mutation gate filters out implementations with weak test coverage before spending model tokens on jury review.

### Threshold calibration

Start with a curated set of 15 specs. Run mutation gate on all locked implementation + test_suite pairs. Record kill rates. Set threshold at the 25th percentile (i.e., 75% of specs should pass). Adjust after each golden run. Threshold lives in `FactoryConfig`, not hardcoded.

## Risks

| Risk | Mitigation |
|---|---|
| Mutation testing is slow | Limit to 10 operators; cache mutants by implementation hash; skip if implementation hasn't changed |
| Some correct code is inherently hard to mutate-test (e.g., passthrough wrappers) | Allow override via `mutation_gate: skip` in spec custom_fields, with principal approval |
| Threshold too high rejects good implementations with adequate tests | Calibrate on curated set before enforcing; make threshold configurable per spec |

## Blocking

Phase 4 (jury gates) or Phase 5 (first real workload). Should be benchmarked before the frontier judge becomes load-bearing. Acceptable to build in parallel with Phase 3 if capacity allows.

## Next step

1. Create `src/factory/mutation_gate.py` with AST mutator and runner
2. Add `_run_mutation_test()` to `evaluate_implementation()` behind config flag
3. Benchmark on 5 curated GR004/005 spec pairs
4. Add `mutation_threshold` to `FactoryConfig`
5. File RFC-007 resolution with empirical threshold
