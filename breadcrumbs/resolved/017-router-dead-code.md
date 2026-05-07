---
number: "017"
title: "Router is dead code — route() never called by gate_process"
severity: medium
status: implemented
kind: design
author: test-audit
date: "2026-05-07"
tags: [router, gate, stage-5]
resolution: wired-into-gate_process
---

## Background

`router.py` defines `route()` and `Route`, but `gate_process.py` never called `route()`. Instead it hardcoded transition names (`gate_pass`, `gate_fail`) directly in `process_gate_item`. The router and gate_process had been aligned on the diagnostics schema (both now write `message` + `messages`), but they remained disconnected in the control flow.

As Phase 2 adds more roles (test_author, implementer, cross_family_reviewer, frontier_judge), failure routing becomes more complex (spec §4: gate_fail → implementer OR test_author; jury disagreement → interface architect). The router's purpose is to encode this routing logic in one place.

## Resolution (2026-05-07)

**Wired router into gate_process now (Option 1).**

Modified `process_gate_item` to call `route()` for both pass and fail transitions. The diagnostics construction now comes from `routing.custom_fields_update`, keeping routing logic centralized. Low risk for Phase 1 (same routing table), sets up architecture for Phase 2. Added `route` import to `gate_process.py`.

Integration tests already exercise `gate_pass`/`gate_fail` transitions; they now implicitly test the router path end-to-end.
