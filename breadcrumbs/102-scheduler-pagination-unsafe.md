---
number: "102"
title: Scheduler idempotency is pagination-unsafe O(N)
description: >
  _ensure_downstream_item queries ALL work items of the target type and iterates
  through them. If there are more items than page_size, the existing item may be on
  a skipped page, causing duplicate downstream items. This was acknowledged in BC-032
  as "accepted for Phase 3" but remains a live correctness risk at scale.
severity: high
status: proposed
kind: bug
author: opencode-adversarial-review
date: "2026-05-11"
tags: [scheduler, idempotency, pagination, stage-2]
related: ["032", "026"]
---

## Proposed fix

1. Query with a composite filter that includes the ref_field value, or
2. Paginate through all pages (loop while page.has_more), or
3. Add a substrate-level `has_work_item_with_custom_field` API.

## Affected file

- `src/factory/scheduler.py`
