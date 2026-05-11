---
number: "117"
title: "Scheduler pagination has no integration test — requires >100 same-type work items to exercise"
severity: medium
status: implemented
kind: improvement
author: glm-5-1
date: "2026-05-11"
tags: [scheduler, pagination, testing, dep-substrate-030]
related: ["102"]
---

## Problem

The BC-102 pagination fix adds a `while` loop with `has_more`/`cursor` to `_ensure_downstream_item`. However, no test exercises multi-page behavior because no fixture creates >100 work items of the same type. The `page_size` default is 50, so the existing pagination code path is completely untested.

If substrate changes the `QueryPage` API (renames `has_more` or `cursor`), the scheduler will silently stop paginating and fall back to single-page behavior — the exact bug BC-102 fixed.

## Affected files

- `src/factory/scheduler.py` — pagination loop
- `tests/test_scheduler_idempotency.py` — no multi-page test

## Proposed fix

Add a test that patches `query_work_items` to return paginated results (page 1 with `has_more=True`, page 2 with `has_more=False`), asserting the scheduler walks all pages rather than stopping after the first.