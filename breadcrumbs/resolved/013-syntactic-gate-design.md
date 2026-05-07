---
number: "013"
title: "Gate is syntactic-only — semantic gating is the central Phase 2 design question"
severity: high
status: implemented
kind: design
resolution: option-c-hybrid
author: opcode-golden-run-001
date: "2026-05-07"
tags: [gate, stage-5, stage-6, stage-7, jury, phase-2]
related: ["004"]
---

## Background

`evaluate_interface_spec()` checks: file exists, non-empty, valid Python syntax, no implementation bodies, AC references present. All syntactic.

A .pyi that defines `acquire_claim(x: int) -> bool` with `"""Satisfies AC-06."""` would pass the gate just as cleanly as the correct variant-type version from the golden run.

The semantic spot-check on 01/04/07 confirmed Claude happened to produce correct interfaces this run. But nothing in the factory's current machinery *enforces* that. As role count multiplies in Phase 2, the probability that a role produces syntactically valid but semantically wrong output increases multiplicatively.

## Why this is the central Phase 2 design question

Phase 1 has one role (interface_architect) with one channel (Claude). Semantic correctness is a function of prompt quality and model capability — both are constant for a given run. Phase 2 adds at least four more roles (test_author, implementer, cross_family_reviewer, frontier_judge) in a sequential pipeline where each role consumes the prior role's artifact. A semantic error in the interface propagates to the tests, which then look correct to the implementer, which then looks correct to the reviewer — a chain of syntactically valid but semantically vacuous artifacts, none of which any gate catches.

The spec (§6, §7) already calls for:
- **Stage 6:** Cross-family review (different model family reviews against AC)
- **Stage 7:** Frontier judge jury (2-3 Tier-A models independently judge)

These are the semantic gates. Phase 2 must make them real.

## Options

1. **Build semantic gates inline during Phase 2 role-by-role roll-out.** Each new role gets its semantic gate designed and implemented alongside it. Most natural fit: implementer gets cross-family review as its paired gate.

2. **Build semantic gates as a Phase 2 sub-phase, after all roles are mechanically correct.** Validate pipeline topology first, then add judgment. Risk: you ship a pipeline that produces syntactically valid but wrong output without knowing it.

3. **Hybrid: add structural-semantic checks to existing mechanical gates as stopgaps.** E.g., check that test function names reference the interface they're testing, that implementation imports match the interface's exports, that reviewer comments reference specific AC IDs. Cheap, deterministic, catches obvious vacuities before a model judge runs.

## Acceptance criteria

- Decision on strategy recorded in this breadcrumb (closure note).
- No code until Phase 2 begins — this is a design breadcrumb, not a build ticket.
- When Phase 2 starts, this breadcrumb is the first thing to read.

## Resolution (2026-05-07)

**Decision: Option (c) — hybrid structural-semantic stopgaps in mechanical gates.**

Rationale: Options (a) and (b) both carry risk. Option (a) couples semantic-gate design to each role's roll-out, making Phase 2 scope unpredictable. Option (b) ships a pipeline with known vacuity until a sub-phase completes. Option (c) adds cheap, deterministic checks that catch obvious vacuities before any model-judge runs — and these checks compose naturally with the existing mechanical-gate infrastructure.

**Implemented structural-semantic checks for interface_spec:**

1. **Function count > 0** — a .pyi with no functions/classes/enums is vacuous regardless of AC references.
2. **Return types present** — every top-level function must have a return annotation; `def foo()` with no `->` is ambiguous.
3. **Parameter names present** — every function parameter must have a name (not just `self` for methods); bare `def f()` is vacuous if ACs require inputs.
4. **AC-to-function binding** — each declared AC must be referenced by at least one function/class docstring; an AC that appears only in prose (not attached to a structural element) is likely test theater.

These are all deterministic AST checks — no model invocation required. They catch the class of "syntactically valid but semantically vacuous" artifacts that BC-013 identifies (e.g., `acquire_claim(x: float) -> None` with `"""Satisfies AC-06."""` would fail the return-type check since the spec says it returns a variant type).

Phase 2 will extend this pattern: test suites must reference the interface they test, implementations must import the interface's exports, reviewer comments must reference specific AC IDs. Same principle — deterministic before model.
