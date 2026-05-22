---
number: "190"
title: "Scheduler downstream dedup is racey and O(N); handoff iteration unfair"
severity: high
status: implemented
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

**Dedup lock (correctness fix).** Substrate's `acquire_claim` is tied to an existing work-item UUID and has no general advisory-lock primitive for arbitrary keys, so a per-(source_id, downstream_type) `threading.Lock` stored in a `WeakValueDictionary` was used instead. The registry meta-lock ensures atomic lock creation; the WeakValue dictionary prevents unbounded growth. The entire existence-check + create block now runs under this lock, closing the TOCTOU window. Limitation documented: guards within a single scheduler process only; multi-process deployments would need a Postgres advisory lock.

**Indexed lookup (perf).** An in-memory `_existence_cache: dict[(source_id, downstream_type), bool]` is populated on first scan-hit and on create. Subsequent calls within the same process return immediately without touching `query_work_items`. A test verifies zero query calls on cache hit.

**Fairness.** `_poll_handoffs` calls `random.shuffle` on a copy of `config.stage_topology` each cycle. A test patches `random.shuffle` with a recorder and asserts the order varies across 20 cycles.

**Deferred.** No indexing was added to substrate itself (no sidecar table, no custom-field filter) — the in-memory cache is sufficient for Phase 2/3 single-scheduler deployments and requires no schema changes.

**Files changed:**
- `src/factory/scheduler.py` — dedup lock registry, existence cache, shuffle in `_poll_handoffs`, full `_ensure_downstream_item` rewrite
- `tests/test_bc190_scheduler_dedup_fairness.py` — 5 new tests (dedup concurrency, idempotency, cache hit/miss, fairness)
