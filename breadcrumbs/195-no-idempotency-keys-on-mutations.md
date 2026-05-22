---
number: "195"
title: "No idempotency keys on substrate mutations — crash-retry creates duplicates"
severity: medium
status: proposed
kind: bug
author: external-review
date: "2026-05-22"
tags: [runner, gate, telemetry, race]
related: ["194"]
---

## Problem

No `event_id` parameter is passed to any substrate mutation in `src/`. Substrate supports `event_id: uuid.UUID | None = None` on `create_work_item`, `transition`, `acquire_claim`, `release_claim`, `create_link`, `remove_link`, and `update_not_before` — but sf2 never uses it.

If the process crashes between a successful mutation and the acknowledgment (or between a mutation and writing local state), a retry will create duplicate events. This is the classic at-least-once delivery problem.

## Evidence

- Zero occurrences of `event_id` as a parameter in `src/`
- Substrate API accepts `event_id` on 8 mutation methods (confirmed via substrate `__init__.py`)
- Runner and gate_process have crash-retry loops that could re-execute mutations

## Fix

Generate a deterministic `event_id` (e.g., `uuid.uuid5(NAMESPACE, f"{work_item_id}:{transition_name}:{attempt}")`) before each mutation call. Pass it to the substrate method. This makes mutations idempotent across retries.
