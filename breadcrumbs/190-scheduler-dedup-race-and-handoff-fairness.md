---
number: "190"
title: "Scheduler downstream dedup is racey and O(N); handoff iteration unfair"
severity: high
status: proposed
kind: bug
author: claude
date: "2026-05-18"
tags: [scheduler, race, fairness, phase-3]
related: []
---

# BC-190 — `_ensure_downstream_item` can double-create; `_poll_handoffs` starves slow stages

## Problem

`src/factory/scheduler.py:91-166` (`_ensure_downstream_item`) paginates every downstream item of the target type, linearly scans for `ref_field == source_id`, then creates+links if not found. Two issues:

1. **Race.** Two scheduler instances (or one scheduler + an event-driven re-trigger) can both observe "no downstream item exists" and both call `sub.create_work_item`. Result: duplicate downstream items. There is no `acquire_claim`-style lock per `(source_type, source_id, target_type)` handoff.
2. **Cost.** Pagination over every downstream item to find one ref is O(N) per handoff. With multiple channels in Phase 3, handoff frequency scales.

Additionally, `_poll_handoffs` (same file, the handoff loop) iterates `config.stage_topology` in declaration order with no fairness. A noisy upstream stage can starve a slow downstream stage of poll attention until its own backlog is drained.

## Proposed fix

1. **Dedup lock.** Acquire a substrate claim keyed by `(handoff_id, source_id)` before the existence check, or rely on a unique constraint on `(downstream_type, ref_field, source_id)` enforced at create time. Substrate's `acquire_claim` semantics fit; alternatively a SQL `INSERT ... ON CONFLICT DO NOTHING` if we expose it.
2. **Indexed lookup.** Maintain an explicit `(source_id, downstream_type) → downstream_id` index (substrate custom field or sidecar table) so the existence check is O(1) instead of O(N).
3. **Fairness.** Randomize `stage_topology` iteration order each poll cycle, or maintain a per-handoff `last_polled_at` and visit oldest-first.

(1) is the correctness fix and must land before Phase 3 widens the channel pool. (2) and (3) are performance/operational.

## Acceptance criteria

1. Test: two concurrent `_ensure_downstream_item` calls for the same source produce exactly one downstream item.
2. Bench (or test that asserts call count): the existence check does not paginate the full downstream-type set.
3. Test: a stage that takes 10x longer than its sibling does not block the sibling from being polled.

## Resolution

_(pending)_
