---
number: "026"
title: "Scheduler idempotency — global has_link_type query skips unrelated sources"
severity: medium
status: implemented
kind: bug
author: session-8
date: "2026-05-07"
tags: [runner, gate, stage-4]
resolution: per-source-custom-fields-ref-check
---

## Background

`_ensure_downstream_item` in `scheduler.py` used `has_link_type` in `query_work_items` to check whether a downstream item already existed. This query is global — it returns work items that have ANY outgoing link of the given type. Once item A had a `test_suite` with a `derived_from` link, the scheduler would skip creating a `test_suite` for item B as well, because the global check found at least one match.

## Fix applied (2026-05-07)

Replaced the global `has_link_type` query with a per-source check: query all downstream items of the target type, then check if any has a `custom_fields` ref (e.g., `interface_ref`, `test_suite_ref`) matching the source work item ID. O(n) but correct for Phase 2's single-channel sequential mode.

Note: A cleaner solution would use a regista `query_links(to_work_item_id=X, link_type=Y)` API, which does not yet exist.

Tests in `test_scheduler_idempotency.py`.
