---
number: "030"
title: "Real Regista read_events should support composite filters (work_item_id + transition)"
severity: medium
status: resolved
kind: design
author: opencode
date: "2026-05-07"
tags: [dep-regista-040, api-contract, conformance]
related: ["040"]
---

## Problem

`Regista.read_events` documents and enforces "exactly one filter dimension" — providing `work_item_id` silently ignores `transition`, `actor_id`, etc. `InMemorySubstrate` was changed to match this behavior in BC-040, but the restriction is unnecessarily limiting: SF2 tests need `read_events(work_item_id=X, transition="channel_fail")` to verify specific events, and the current workaround (query by `work_item_id` then filter in Python) is wasteful for large event logs.

## Proposal

Real backend `read_events` should support composable filters via AND-composition in SQL. This is a straightforward change — the existing `_read_by_work_item` query already scopes to a work item; adding `AND transition = %s` is trivial. The "exactly one dimension" constraint should be relaxed to "at least one dimension."

## Impact

- SF2 test helper `events_by_transition` becomes unnecessary once this lands
- InMemorySubstrate can revert to composable filters (restoring the pre-BC-040 behavior)
- No breaking change — single-dimension queries still work identically