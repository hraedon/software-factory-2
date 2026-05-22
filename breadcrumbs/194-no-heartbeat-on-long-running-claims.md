---
number: "194"
title: "No heartbeat on long-running model claims — claim theft risk"
severity: high
status: proposed
kind: bug
author: external-review
date: "2026-05-22"
tags: [runner, gate, race, failure-routing]
related: []
---

## Problem

Model invocations in `runner.py` and `gate_process.py` can take 1–10 minutes. Claims have a 300s TTL, but neither module calls `heartbeat_claim()`. If a model invocation exceeds the TTL, the claim expires and another process can steal the work item, leading to double-processing or data corruption.

Substrate provides `heartbeat_claim(work_item_id, actor_id, ttl_seconds)` exactly for this purpose.

## Evidence

- `src/factory/runner.py` — acquires claim at line 191, invokes model (unbounded time), never heartbeats
- `src/factory/gate_process.py` — acquires claim at line 96, runs gate (unbounded time), never heartbeats
- Zero calls to `heartbeat_claim` anywhere in `src/`
- Default TTL is 300s (5 min); model calls routinely exceed this

## Fix

Wrap model invocations in a heartbeat thread or use periodic `heartbeat_claim()` calls during long-running operations. The `coalesce_threshold` parameter on `heartbeat_claim` prevents event spam.
