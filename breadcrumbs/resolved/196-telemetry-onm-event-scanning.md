---
number: "196"
title: "Telemetry reads all events for all work items — O(n*m) scaling"
severity: medium
status: implemented
kind: improvement
author: external-review
date: "2026-05-22"
tags: [telemetry]
related: []
---

## Problem

`telemetry.py` calls `sub.query_work_items()` to get all items, then for each item reads its full event history. This is O(n_items * m_events_per_item) — scales linearly with project size. For large projects, this becomes prohibitively slow.

## Evidence

- `telemetry.py` line 101: `sub.query_work_items(workflow_name=..., workflow_version=..., page_size=1000)` — fetches all items
- `telemetry.py` line 292: iterates items to collect gate attempts
- `telemetry.py` line 603: iterates items again for exit criteria
- No server-side filtering by event type or time range

## Fix

1. Added `_query_work_items_and_events()` in `telemetry.py` which fetches all work items once and reads events per work item once into dicts keyed by work_item_id.
2. Updated all four telemetry consumers to accept caches:
   - `collect_gate_attempts(sub, config, events_by_id=...)`
   - `compute_exit_criteria(sub, config, attempts, work_items=...)`
   - `collect_contract_complaints(sub, config, work_items=..., events_by_id=...)`
   - `collect_routing_hints(sub, config, work_items=..., events_by_id=...)`
3. `run_telemetry_report()` and `run_telemetry_verify()` now build the cache once and pass it to each collector, reducing substrate event reads from 4×N to 1×N per run.
4. No substrate API changes required — fix is entirely client-side.
