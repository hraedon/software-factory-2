---
number: "CLASS-011"
title: "Budget/Retry/Escalation Loop Control"
severity: critical
status: active
kind: defect-class
author: rfc-016-backfill
date: "2026-05-15"
tags: [runner, escalation, budget, retry]
related: ["037", "046", "062", "139", "143", "158", "RFC-005"]
---

## Shape

Work items that cannot succeed are not transitioned to a terminal state; instead, they cycle through claim→fail→release→claim indefinitely, burning model budget and producing zombie items.

## Systemic cause

The runner's claim-process-release loop has no global budget enforcement. Early implementations released the claim on failure without transitioning the work item to a terminal state. The attempt_threshold mechanism existed but was not wired to terminal transitions for all failure kinds. Escalation was added incrementally per failure kind rather than as a universal property of the claim loop.

## Systemic fix

Universal escalation: every diagnostic kind present in `_ESCALATABLE_KINDS` routes to `cannot_proceed` at `attempt_threshold`. The `claim_near_budget` guard must always transition to terminal, not just release. RFC-005's composable handler pipeline makes adding new escalatable kinds a handler insertion, not a dispatch-table edit.

## Trigger condition

≥5 instances (current: 6). Systemic fix deployed; monitoring for new instances.

## Instances

| BC   | Symptom |
|------|---------|
| 037  | Escalation routing is a no-op for non-interface_spec types |
| 046  | Runner resubmits gate-rejected artifacts on subsequent claims |
| 062  | Resume-on-gate-fail still wastes budget |
| 139  | Review and jury gate failures never escalate — infinite retry loop |
| 143  | claim_near_budget releases without terminal transition |
| 158  | Outcome-verifier routing_hint extracted but never consumed |