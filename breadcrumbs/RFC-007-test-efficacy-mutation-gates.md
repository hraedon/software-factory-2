---
number: "RFC-007"
title: "Test efficacy scoring via mutation testing gates"
severity: high
status: proposed
kind: design
author: opencode
date: "2026-05-09"
tags: [rfc, gate, jury, stage-7, dep-v1-107]
related: ["RFC-005", "RFC-002"]
---

## Summary

Spec §8.9 explicitly acknowledges **test theater** as an open risk: *"subtle tautologies will get through"* even with a frontier-judge gate checking "do these tests demonstrate AC is met?" The current mitigations are:
- Outcome verification (Stage 9)
- Principal's outcome review (Stage 10)

Neither is automatic or mechanical. v1 addressed this with AST-based mutation testing (Bite Score) applied to both generated projects and the factory's own test suite (`scripts/self_mutation_test.py`). v2 has no equivalent.

This RFC proposes a **mutation-testing gate** that runs after a test suite + implementation pair is locked, before the frontier judge is invoked.

## Proposed mechanism

1. **Mutant generation:** Apply a small, deterministic set of semantic mutations to the locked implementation:
   - Replace `==` with `!=`
   - Replace `>` with `<`
   - Replace `+` with `-`
   - Delete early-return guard clauses
   - Swap branch bodies in `if/else`
   - Replace constant values with sentinel values of the same type
2. **Test execution:** Run the locked test suite against each mutant.
3. **Scoring:** A "killed" mutant is one where at least one test fails. Compute `kill_rate = killed / total_mutants`.
4. **Gate decision:** If `kill_rate < threshold` (suggest 0.6–0.7), the artifact pair fails the gate with `diagnostic_kind = "test_efficacy"`.
5. **Routing:** Route back to `test_author` (below threshold) or `interface_architect` (at/above threshold), similar to other escalatable kinds.

## Why this matters for v2

The three-role pipeline's correctness guarantee depends on "tests are the contract." If the contract is vacuous (tautological tests that always pass), the implementer can produce any code and the mechanical gates will green-light it. The frontier judge is supposed to catch this, but:
- It is expensive (multi-model)
- It is not deterministic
- It may itself miss tautologies (especially if the model that wrote the tests also reviews them)

A mechanical mutation-testing gate is cheap, deterministic, and catches the exact failure mode §8.9 worries about.

## Deferred decisions

- **Mutation operator set:** Full mutation testing (e.g., `mutmut`) is slow. A minimal, AST-driven operator set (~10 operators) may suffice for v2's scale.
- **Threshold calibration:** Must be established empirically on curated specs before enforcing.
- **Scope:** Apply only to `implementation` + `test_suite` pairs, or also to `interface_spec` stubs?
- **Tool reuse:** Use an existing library (`mutmut`, `cosmic-ray`) or build a small custom mutator to avoid heavy dependencies.

## Phase needed

Phase 4 (jury gates) or Phase 5 (first real workload). Should be benchmarked before the frontier judge becomes load-bearing.

## Precedent

v1 Breadcrumb 107 (Test Efficacy Scoring) and BC-186 (Phantom Coverage Detection) both show that without empirical test-quality measurement, "tests pass" is a weak correctness signal.
