---
number: "RFC-033"
title: "Guardrail lifecycle: tag preconditions, audit on invariant change"
severity: medium
status: proposed
kind: design
author: claude
date: "2026-05-17"
tags: [process, safety, wrapper, guardrails, v1-lesson, meta-defense]
related: ["RFC-030", "RFC-031", "RFC-032"]
---

## Motivation

Three wrapper guardrails were retired this week after falsely killing otherwise-healthy runs:

- **commit 1710792** — idle-detection threshold (5 min) fired on an attended run after role timeouts doubled from 300s to 600s. The threshold was never updated. Killed a run that was working normally.
- **commit 6913f19** — `gate_fail_cross_family_review >= 3` fatal. When BC-180 and BC-185 fixed the CUSTOM_FIELD_VIOLATION crash-loop and gave gate_fail a clean routing path, 3+ cross-family review failures became normal pipeline activity (gemini reviewing K2 impls across distinct items), not a crash signal. The guardrail survived past its precondition.
- **commit f1fc1ef** — `claim_near_budget >= 5` fatal. BC-139 (runner hard-stop) and BC-186 (gate hard-stop) made every claim_near_budget emit a clean cannot_proceed transition. The runaway signal the guardrail detected was structurally eliminated. The guardrail survived past its precondition. It fired in GR-038 on a clean ALL-PASS run.

All three were correct when added. None were re-evaluated when the underlying state machine matured. This is the same shape as v1's gate accumulation — where gates added for a specific failure mode were never retired once that mode was fixed — but applied to safety mechanisms rather than quality gates.

## Proposal

Every guardrail — defined as any code path that aborts or escalates an otherwise-progressing process based on a heuristic threshold — must carry inline comments declaring:

1. **Precondition BCs/invariants**: the named BCs or state-machine invariants whose presence makes the original failure mode possible. No precondition → the guardrail is defending against a phantom.
2. **Audit trigger**: a stated rule of the form "re-evaluate when [precondition X] changes."

The audit trigger fires whenever any of the following occur:

- A precondition BC's status changes to `implemented` or `obsolete`.
- A precondition invariant is changed by an RFC marked `implemented`.
- The guardrail's threshold value is being tuned (drift in calibration is itself a signal that the underlying state machine has moved).

The convention requires two comment lines per guardrail:

```python
# Precondition: <BC or invariant that makes the failure mode possible>
# Audit trigger: re-evaluate when <specific condition>
```

## Worked Example

The three retired guardrails would have been tagged as follows:

**Idle threshold (max_idle_cycles):**
```
# Precondition: no role timeout exceeds the idle window (idle_window = max_idle_cycles * interval)
# Audit trigger: re-evaluate when any role timeout value changes
```
Failed audit: role timeouts went from 300s to 600s; the 5-min idle window did not move. The tag would have surfaced this at the moment of the timeout change.

**`gate_fail_cross_family_review >= 3` (now retired):**
```
# Precondition: BC-180 not implemented (no clean routing path for cross_family_review gate_fail)
# Audit trigger: re-evaluate when BC-180 closes
```
Should have retired at BC-185 implementation (routing fix landed). Tag would have flagged it.

**`claim_near_budget >= 5` (now retired):**
```
# Precondition: BC-139 not implemented (no runner hard-stop on attempt exhaustion)
# Audit trigger: re-evaluate when BC-139 closes
```
Should have retired at BC-139 implementation. Tag would have flagged it.

## Why Inline Comments, Not a Separate Registry

The guardrail and its preconditions need to drift in lockstep. A separate registry file would itself drift — anyone touching the guardrail code reads the comment; almost no one reads a registry. Inline comments are the only form of documentation that has shown durable locality in this codebase (precedent: the existing claim_near_budget and cross_family_review post-retirement comments in `_monitor_logs` that correctly narrate why those signals are warn-only).

## Operational Cost

Small. Tagging a guardrail takes one two-line comment block. Reviewing when a precondition changes is a few minutes per audit — searching for the BC number in the scripts directory. Cost is amortized against the wall-clock cost of false-positive fatals: this week alone, one wasted 25-minute run and a near-miss ALL-PASS killed at the last minute.

## Acceptance Criteria

- **AC-1**: This RFC filed.
- **AC-2**: The remaining live guardrails in `scripts/agent_golden_run.py` tagged with their preconditions:
  - The `DANGER_SIGNALS` table (each entry).
  - The `channel_invoke_failed >= 5` fatal threshold.
  - The `max_idle_cycles` idle-detection path.
- **AC-3**: A note in `AGENTS.md` "Agent-mediated golden runs" section reminding implementers to tag new guardrails per RFC-033.

## Out of Scope

Substrate-side guardrails such as `claim_ttl` enforcement — those are state-machine invariants (hard semantic constraints), not heuristic thresholds calibrated to empirical failure rates, and they do not drift the same way. This RFC covers only the heuristic-threshold category.
