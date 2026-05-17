---
number: "CLASS-005"
title: "Inner Gate vs Outer Gate Ruleset Divergence"
severity: critical
status: active
kind: defect-class
author: rfc-016-backfill
date: "2026-05-15"
tags: [gate, inner-gate, outer-gate, rfc-011]
related: ["075", "079", "082", "085", "086", "114", "122", "123", "124", "131", "154", "RFC-011"]
---

## Shape

The inner gate (pre_gate.py) and outer gate (gate.py) are independently maintained implementations of overlapping checks. When one is updated, the other is not, leading to divergent behavior: inner pass + outer fail (wastes model budget) or inner fail + outer pass (wastes inner-gate retries).

## Systemic cause

Two parallel implementations of overlapping conceptual gates exist because of architectural timing: the inner gate runs pre-submission (fast, in-process) and the outer gate runs post-submission (full, via gate_process). They share no code, no test fixtures, and no shared gate-evaluation module. There is no mechanism that forces a change to one to propagate to the other.

## Systemic fix

RFC-011: Unified gate evaluation layer — extract shared subprocess execution layer to eliminate drift between inner and outer gate implementations.

## Trigger condition

≥5 instances (current: 11). Already justifies the systemic fix proposed in RFC-011.

## Instances

| BC   | Symptom |
|------|---------|
| 075  | Inner gate loop created for implementer (pre-submission validation) |
| 079  | Inner gate silently passes on tool-not-found — contradicts outer gate fix |
| 082  | Outer gate and inner gate have divergent tool path resolution |
| 085  | Interface spec inner gate — import smoke check added |
| 086  | Test suite inner gate — pytest --collect-only added |
| 114  | pre_gate _run_ruff_fast mutates artifact (different from outer gate tempdir) |
| 122  | Prompt pre-flight checklists — inner gate first-pass improvement |
| 123  | Inner gate auto-fix diverges from outer gate |
| 124  | Selective ruff rule set — inner gate rules diverge from outer |
| 131  | Runtime import resolution feedback — inner gate only |
| 154  | _run_ruff_fast modifies artifact in-place inside inner gate |

## Status under RFC-030

This class is in the **RFC-filed-but-dormant** state. RFC-011 exists and correctly identifies the invariant (unified gate evaluation layer), but no implementation has landed and RFC-011's status remains `proposed`. Under RFC-030's block rule, no new BC may be added to the instances table above until one of the following occurs:

- **Path A** (recommended): Assign an owner to RFC-011, move its status to `in_progress`, and set a target run for validation. This is the correct path given 11 instances at critical severity — the cost of the invariant is bounded and the cost of continued symptom-fixing is unbounded.
- **Path B** (available but discouraged): The principal writes and signs a `symptom-fixed-because` rationale in this file answering what cost the unified gate layer would carry that exceeds the cost of continued per-instance fixes. Given 11 critical instances with no sign of the class saturating, the analysis is likely to favor Path A, but the call is the principal's.

The next engineer who encounters an inner/outer gate divergence and attempts to add a row here is the forcing function: surface this decision explicitly rather than adding another symptom-fix.