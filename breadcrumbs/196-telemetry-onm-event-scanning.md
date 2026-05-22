---
number: "196"
title: "Telemetry reads all events for all work items — O(n*m) scaling"
severity: medium
status: proposed
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

Add substrate support for filtered event queries (e.g., `query_events(event_types=["gate_pass", "gate_fail"])`) to push the aggregation server-side. Short-term: cache the event list per telemetry run instead of re-reading for each analysis pass.
