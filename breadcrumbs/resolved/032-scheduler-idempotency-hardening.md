---
number: "032"
title: "Scheduler O(n) idempotency and hardcoded dispatch need hardening"
severity: medium
status: implemented
kind: improvement
author: opencode
date: "2026-05-07"
tags: [scheduler, runner]
related: ["058"]
---

## Problem

`scheduler.py` has two design weaknesses identified in the Phase 2 reflection:

1. **O(n) idempotency check**: `_ensure_downstream_item` queries all work_items with `has_link_type` and then checks custom_fields in Python. The right fix is a substrate `query_links(to_work_item_id=X, link_type=Y)` API (currently missing).

2. **Hardcoded `_ref_field_for` dispatch**: The mapping from work_item_type to custom_field name (`interface_spec → interface_ref`, `test_suite → test_suite_ref`) is a dict lookup that duplicates workflow knowledge. It should be derived from the workflow YAML's work_item_type definitions.

## Proposal

1. Request `query_links` API from substrate (or accept the O(n) cost for Phase 2 single-channel mode, to be replaced before Phase 3 parallelism).
2. Make `_ref_field_for` read from the registered workflow definition instead of a hardcoded dict.

## Impact

O(n) is acceptable for Phase 2's single-channel sequential mode. Both issues must be resolved before Phase 3 adds parallel workers.