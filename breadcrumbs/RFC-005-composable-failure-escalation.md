---
number: "RFC-005"
title: "Composable failure/escalation architecture — v1 imperative if/elif chain grew unbounded"
severity: medium
status: proposed
kind: design
author: adversarial-review
date: "2026-05-08"
tags: [failure-routing, router, dep-v1-failure-loop]
related: ["037", "046"]
---

## Problem

v1's `failure_loop.py` evolved: simple retry loop → tiered escalation (P0-P3) → fix verification → testability seams. Each layer was added without removing the previous one. The result: duplicate semantic loop detection (two independent checks), a legacy `MAX_RETRIES = 3` constant surviving alongside the tiered system, and escalation logic duplicated between `failure_loop.py` and `phase_runner.py`.

v2's `router.py` is currently 226 lines with an imperative `if/elif` chain in `_PHASE2_DISPATCH` and a procedural `route()` function. It's clean for 3 stages but will grow with:
- Phase 3: cross-family reviewer route targets
- Phase 4: jury disagreement routes (2-of-3 quorum vs. deadlock)
- Phase 8 integration: cross-cutting test failure routes

The same unbounded growth pattern will recur.

## Proposal

Design the failure/escalation system as a composable pipeline (like the stage system itself):
1. Each `DiagnosticKind` maps to a `RouteHandler` with `can_handle(diagnostic) -> bool` and `build_route(diagnostic, context) -> Route`.
2. Handlers are composed in priority order; the first handler that `can_handle` wins.
3. Escalation is a separate `EscalationHandler` composed *around* the route handler: `EscalationHandler.wrap(handler, threshold=N)`.
4. New failure modes (jury disagreement, integration test failure) add new handlers without modifying the dispatch table.

## Dependencies

Awaits Phase 4 when jury disagreement introduces a new failure class. The refactor should happen before adding that class — doing it after (as v1 did) is what creates the legacy-survival pattern.
