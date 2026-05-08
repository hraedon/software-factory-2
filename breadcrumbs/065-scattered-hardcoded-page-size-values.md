---
number: "065"
title: "Scattered hardcoded page_size values — not derived from FactoryConfig"
severity: medium
status: proposed
kind: bug
author: adversarial-reviewer
date: "2026-05-08"
tags: [runner, gate, telemetry]
related: []

## Summary

Five different hardcoded `page_size` values across four files, none derived from configuration:

| File | Line | Value | Impact if exceeded |
|---|---|---|---|
| `runner.py` | 110 | 10 | Work items silently not claimed |
| `gate_process.py` | 75 | 10 | Gate items silently skipped |
| `scheduler.py` | 77 | 50 | Locked items for handoff silently skipped |
| `scheduler.py` | 107 | 100 | Duplicate downstream check silently incomplete |
| `telemetry.py` | 37 | 200 | Events beyond 200 silently dropped |

A run with more than 10 items in `new` at once (runner/gate) or more than 50 items in `locked` (scheduler) or more than 200 events per work-item (telemetry) would produce silently incorrect results with no error.

## Fix

Add `query_page_size: int = 50` and `telemetry_event_limit: int = 500` to `FactoryConfig`. Replace all 5 hardcoded values with config references. Use a single shared page_size for runner/gate/scheduler queries.
