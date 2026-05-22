---
number: "120"
title: "Implementer-initiated interface amendment — structured cannot_proceed for contract renegotiation"
severity: medium
status: deferred
kind: design
author: gemini-adversarial-review + openus-refinement
updated: "2026-05-22"
date: "2026-05-11"
tags: [runner, spec, implementer, interface_architect, stage-2, stage-4, rfc, deferred]
related: ["077", "RFC-013", "134", "RFC-016"]
---

## Problem

Spec §3.8 says "errors loop back to contract revision, not worker retry." §4 routes jury disagreement back to Stage 2 (interface_architect). The mechanism exists, but it only triggers on jury failure — not on the implementer discovering mid-implementation that the interface signature is wrong.

The implementer is the cheapest party to detect a broken contract (it has the interface, the tests, and the runtime errors in front of it) and the most expensive one to silence. Currently, if the implementer discovers a missing parameter or wrong abstraction, it has two bad options:

1. Write unnatural, over-complex code to satisfy the broken contract (wasting model budget on contortions).
2. Escalate via `cannot_proceed`, which terminates the work item without structured remediation data.

## Evidence assessment (updated 2026-05-22)

The original filing predicted the need based on complexity growth, but **zero instances** have been observed across 38 golden runs (GR-001 through GR-038) spanning 4 fixture shapes (cert-watch-mini, cert-watch full DAG, chain-of-trust, csv-toolkit). All implementer `cannot_proceed` events traced to model-quality issues (syntax errors, import errors, ruff violations), not contract mismatches. The amendment mechanism would not have helped.

Spec §10 codifies a "≥3 instances before adding mechanism" rule for gates. The same discipline applies to design machinery. Telemetry and defect-class instrumentation (BC-128, BC-133) now provide the data to count contract-shaped failures cheaply. We run the count first.

**Reactivation trigger condition 1 assessment (2026-05-22):** 0/3 threshold met. The implementer's inner-gate retry loop (RFC-013) and cross-family review path (BC-145 Phase 1) absorb the failure modes that BC-120 would address. The primary jury_disagree -> interface revision path was exercised end-to-end in GR-038 (4 DAG lineages through all 7 stages). BC-120 remains deferred.

## Clean two-role shape (target design if trigger fires)

If reopened, the implementation **must not** give the implementer architectural latitude. §3.6: "Filling-in roles, not architectural roles. Workers… do not introduce new modules, do not add abstractions, do not invent new types."

The clean shape is two roles, two prompts, two models:

1. **Implementer** emits a structured **contract complaint** (not a diff): `{"status": "cannot_proceed", "complaint_type": "contract", "rationale": "...", "evidence": "..."}`. No `proposed_change`, no diff, no architectural latitude.
2. **Interface_architect** reviews the complaint + evidence against the original ACs. If it agrees, the interface architect authors the amendment. The interface architect stays the contract owner.
3. **Cross-family reviewer** validates the amendment before downstream invalidation (preventing gameability).

The current BC-120 text that proposed `proposed_change: the diff or revised interface signature` is rejected because it violates §3.6.

## Handling (if implemented)

- **Phase 4+:** A Tier-A model (interface_architect role) reviews the complaint against original ACs. If approved, the interface spec is updated, downstream test_suites invalidated, and the implementer proceeds with revised contract.
- **Invalidation scope:** In a cross-module DAG, one bad acceptance reruns half the pipeline. Acceptance bar must require cross-family reviewer concurrence.

## Reactivation trigger

**Reopen when ALL of the following are true:**

1. Phase 5 telemetry shows **≥3 cases** of implementer `cannot_proceed` where the cross-family reviewer agreed the contract was proximate cause.
2. The **inner gate (post-RFC-013)** could not resolve the case via richer diagnostics fed back to the implementer.
3. The **primary path** (jury disagreement → interface revision per §4) has been validated end-to-end on at least one real workload and is known to work.

If the primary path is broken, BC-120 is a workaround for a bug, not a new capability. Fix the primary path first.

## Relationship to RFC-013

RFC-013 (expanded inner-gate feedback) may cover most of the real need. When the implementer gets actionable diagnostics from mypy/pytest/ruff failures, it may self-correct on contract-edge cases without escalating. Running RFC-013 first, then counting what remains, is strictly better than building this mechanism blind.

## Phase placement

**Deferred indefinitely.** The Phase 4 finish line is a clean full-DAG golden run with multi-family jury, failover, and the **existing** §4 jury_disagree → interface revision loop exercised end-to-end on real flow. BC-120 is a parallel mechanism; it waits until the primary mechanism is proven insufficient by data.
