---
number: "120"
title: "Implementer-initiated interface amendment — structured cannot_proceed for contract renegotiation"
severity: high
status: proposed
kind: design
author: gemini-adversarial-review + openus-refinement
date: "2026-05-11"
tags: [runner, spec, implementer, interface_architect, stage-2, stage-4, rfc]
related: ["077", "RFC-013"]
---

## Problem

Spec §3.8 says "errors loop back to contract revision, not worker retry." §4 routes jury disagreement back to Stage 2 (interface_architect). The mechanism exists, but it only triggers on jury failure — not on the implementer discovering mid-implementation that the interface signature is wrong.

The implementer is the cheapest party to detect a broken contract (it has the interface, the tests, and the runtime errors in front of it) and the most expensive one to silence. Currently, if the implementer discovers a missing parameter or wrong abstraction, it has two bad options:

1. Write unnatural, over-complex code to satisfy the broken contract (wasting model budget on contortions).
2. Escalate via `cannot_proceed`, which terminates the work item without structured remediation data.

## Proposed fix

Introduce a structured `cannot_proceed` terminal artifact kind: **Interface Amendment Request**.

When the implementer determines the interface is fundamentally wrong, it outputs a structured JSON artifact (instead of code) containing:

1. `amendment_type`: "interface_amendment"
2. `proposed_change`: the diff or revised interface signature
3. `rationale`: 2-3 sentence explanation of why the current interface is broken
4. `evidence`: the specific error or test failure that triggered the discovery

This piggybacks on the existing `cannot_proceed` transition and the spec's §6 convention that structured failure outputs are first-class artifacts. No new transition type needed.

## Handling

The amendment request would be processed by:

- **Phase 3 (current):** The principal reviews it manually as part of the `cannot_proceed` queue.
- **Phase 4+:** A Tier-A model (the "Systems Architect" / interface_architect role) reviews the diff + rationale against the original ACs. If approved, the interface spec is updated, downstream test_suites are invalidated, and the implementer proceeds with the revised contract.

## Why not a new transition

The spec already has `cannot_proceed` as a terminal state with structured diagnostics. Adding a new `interface_amendment` transition would proliferate the state machine for a case that's currently rare. Structuring the artifact is sufficient; the transition machinery already exists.

## Phase placement

Phase 4 (when jury gates are introduced). The amendment flow is most valuable when paired with automated review — a Tier-A model evaluating the diff against ACs. In Phase 3, the principal handles it manually.

## Evidence

GR-014: the 2 escalations (invalid dataclass, ImportError in generated code) were model quality issues, not contract issues. The amendment mechanism would not have helped here. But as the factory processes more complex specs with genuine interface-level edge cases (multi-module systems, protocol buffers, async interfaces), the implementer will increasingly encounter cases where the spec's interface is wrong, not just the implementation.
