---
number: "RFC-032"
title: "Breadcrumb-velocity circuit breaker: freeze new feature scope when arrival rate exceeds absorption"
severity: medium
status: proposed
kind: design
author: claude
date: "2026-05-17"
tags: [process, breadcrumbs, throughput, v1-lesson, meta-defense]
related: ["RFC-030", "RFC-031", "RFC-013"]
---

## Motivation

v1's April-25 reflection surfaced a failure mode that compounds quietly: "the breadcrumb stack densifies faster than the implementation; one painful run produces a small constellation of breadcrumbs, each costing days to land." The bottleneck shifts from *missing primitives* to *agent+human loop absorption rate* — a subtler ceiling and a harder one to notice in real time.

v2 filed BC-180 through BC-186 (seven BCs in seven days), plus BC-187 today. We are not yet at v1's bottleneck, but the arrival rate is comparable. RFC-013 already prohibits multi-phase BCs without empirical instances; RFC-032 generalizes that discipline from per-BC hygiene to total throughput. The goal is the same: compress the per-symptom-fix loop before the stack grows heavy enough to stall forward motion.

## Proposal

### 1 — The metric

Count BCs filed in the trailing 7-day window whose `status` is `proposed` or `implemented`. Exclude `obsolete`, `deferred`, and `closed` — those are either resolved or intentionally parked and do not represent active queue pressure. RFCs and CLASS files are excluded from the count; only BCs carry implementation debt that accrues.

### 2 — The threshold

Five (5) BCs in the trailing 7-day window.

### 3 — The action

When the count meets or exceeds the threshold, no new feature scope may be started: no new RFCs, no new role implementations, no new gate types, no new fixtures. The freeze holds until the count drops below 5.

Exceptions:
- Bug fixes and tests that directly address an existing open BC are unaffected.
- In-flight work continues to completion — the circuit breaker does not cancel work already started, it prevents new scope from opening.

### 4 — The bypass

A principal may override the freeze by committing a 1-paragraph rationale to `breadcrumbs/principal-overrides.md`. The paragraph must name the override date, the BC count at time of override, and the specific new work being unlocked. The file is append-only; each override is a separate dated entry. The existence of entries in that file is itself a signal — if overrides accumulate, the threshold should be revisited.

## Why this is a circuit breaker, not a budget

A budget says "you may file N BCs per week." A circuit breaker says "if you have filed N BCs, stop opening new scope until the queue catches up." The semantics differ in a meaningful way: a budget is an allowance granted in advance; a circuit breaker is a consequence triggered by observed state. The breadcrumb count here is *consequence*, not *allowance*. The system continues normally at any count below the threshold; enforcement only engages when throughput has already exceeded absorption.

## Worked example

GR-035 through GR-038 produced 9 BCs (178, 179, 180, 181, 182, 183, 184, 185, 186) over approximately 10 days, peaking at 6 BCs in the 7-day window ending 2026-05-17. Under RFC-032, the threshold would have tripped twice during that window. The right response would have been to delay GR-037 by a day to bottom out BC-180/181/182/183/184/185 before launching a new run. We launched anyway; we got lucky that GR-037 surfaced only one new BC (186). Luck is not process.

## Operational cost

A small script (~30 lines) querying `breadcrumbs/` for filed-date and status covers this mechanically. Without the script, `ls breadcrumbs/ | grep "^BC-" | tail -20` plus a manual status check is sufficient — the window is short enough that a quick scan catches it. The discipline cost is the only real cost, and that is the whole point.

## Acceptance criteria

- **AC-1**: This RFC filed.
- **AC-2**: A `scripts/breadcrumb_velocity.py` script (or equivalent) that reads `breadcrumbs/`, computes the 7-day count, and emits a warning when the count is ≥5. May be delivered as a follow-up; the rule is enforceable manually until then.
- **AC-3**: A `breadcrumbs/principal-overrides.md` skeleton, ready to record overrides. Content: a header, the schema (date / BC-count / rationale), and a placeholder `_no overrides recorded_` entry.

## Risks

The threshold may be wrong. Too low and the breaker trips on normal pipeline maturation; too high and it never trips during actual overload. Five is a starting point grounded in v1's empirical pattern — one painful review cycle saturates the queue at roughly that rate. Revisit after one or two real trips; the threshold is not sacred.

## Interaction with RFC-030 and RFC-031

RFC-030 governs what may be filed in a single BC (scope discipline). RFC-031 governs root-cause discipline (don't file a symptom when you can fix the cause). RFC-032 governs aggregate throughput — how many BCs may be in flight simultaneously. All three compress the per-symptom-fix loop from different dimensions and are complementary rather than redundant.
