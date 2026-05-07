---
number: "017"
title: "Router is dead code — route() never called by gate_process"
severity: medium
status: proposed
kind: design
author: test-audit
date: "2026-05-07"
tags: [router, gate, stage-5]
---

## Background

`router.py` defines `route()` and `Route`, but `gate_process.py` never calls `route()`. Instead it hardcodes transition names (`gate_pass`, `gate_fail`) directly in `process_gate_item`. The router and gate_process have been aligned on the diagnostics schema (both now write `message` + `messages`), but they remain disconnected in the control flow.

As Phase 2 adds more roles (test_author, implementer, cross_family_reviewer, frontier_judge), failure routing becomes more complex (spec §4: gate_fail → implementer OR test_author; jury disagreement → interface architect). The router's purpose is to encode this routing logic in one place.

## Options

1. **Wire router into gate_process now** — Replace the hardcoded transitions in `process_gate_item` with `route()` calls. Low risk for Phase 1 (same routing table), sets up the architecture for Phase 2.
2. **Defer to Phase 2** — The router is tested and schema-aligned. Wire it in when the routing table needs to grow. Accept that gate_process and router could drift again.
3. **Delete the router** — If Phase 2 adds routing logic directly in gate_process with role-specific branches, the router abstraction was premature. Remove it and its tests.

## Acceptance criteria

- Decision recorded on which option.
- If option 1: modify `process_gate_item` to call `route()`, add integration test that exercises the router path end-to-end.