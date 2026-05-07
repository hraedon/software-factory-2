---
number: "009"
title: "context_hash → artifact non-determinism; replay tests must assert structure"
severity: high
status: resolved
kind: design
author: opcode-golden-run-001
date: "2026-05-07"
tags: [runner, idempotency, gate, tests, stage-1]
related: ["003"]
---

## Background

`context_hash` is SHA-256 of the deterministic input bundle (spec_section, ac_ids, glossary, prior_failures, prompt_template). It captures prompt determinism but not artifact determinism.

Two invocations with the same `context_hash` can produce different .pyi artifacts because Claude is non-deterministic (sampling variance). The current idempotency logic (`find_resumable_artifact`) resumes from a prior attempt based solely on manifest validity (SHA-256 match on disk). This is correct — it doesn't re-invoke when a valid prior artifact exists. But the test suite never asserts that two artifacts from the same context_hash are structurally equivalent.

If a resumed artifact differs structurally from what a fresh invocation would have produced (different function names, different types defined, different ADT shapes), no test catches it.

## Impact

- Silent correctness risk: a bad artifact from a prior attempt can be resumed without structural validation.
- The 8 idempotency tests pass but assert only SHA-256 integrity, not semantic correctness.
- When `context_hash` changes between attempts (because `prior_failures` changed), the factory does re-invoke — which is correct. But when it doesn't change, the old artifact is reused blindly.

## Proposed approach

Add a structural-equivalence assertion to the replay/idempotency test suite that:

1. Defines a function `structurally_equivalent_pyi(a: str, b: str) -> bool` that parses both .pyi files with `ast` and compares: function names, parameter names and types, class names, Enum member names, Union membership, and docstring AC references. Formatting, whitespace, and docstring prose beyond AC references are ignored.
2. Adds a test: create two artifacts from the same MockChannel fixture, verify they're structurally equivalent despite formatting differences.
3. Adds a test: an artifact with different function signatures (same context_hash, structurally different content) is NOT structurally equivalent — catches the failure mode.
4. Optionally (later phase): add a structural gate to `evaluate_interface_spec` that compares against a reference artifact when one exists.

## Acceptance criteria

- `structurally_equivalent_pyi` passes for identical content.
- `structurally_equivalent_pyi` passes for whitespace/ordering differences that don't change the contract.
- `structurally_equivalent_pyi` fails for different function names, different parameter types, different enum members.
- At least one idempotency test calls `structurally_equivalent_pyi` on the resumed artifact vs the fresh artifact.
