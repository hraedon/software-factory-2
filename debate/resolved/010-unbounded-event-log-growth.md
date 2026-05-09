---
number: "010"
title: "Unbounded event log growth — retention and archival for long-running missions"
author: opencode
date: "2026-05-09"
related: ["RFC-008", "BC-003"]
---

## Context

Substrate's event log is append-only and immutable. Every claim, transition, heartbeat, hook, link, and custom_field update appends an event. There is no deletion, no truncation, and no retention policy defined in the spec.

Factory's talk (Luke) mentions missions running for 16 days, with a goal of 30. At the v2 factory's current event rate:
- 15 interface_specs × 3 attempts average = ~45 submit events
- 15 test_suites × 2 attempts = ~30 events
- 15 implementations × 3 attempts × 5 gate evaluations each = ~225 events
- Plus claims, transitions, scheduler handoffs, dead letters

A single golden run generates ~500 events. A 30-day mission with daily checkpointing and retry loops could generate 10,000+ events per work-item.

## Problem

Unbounded growth has three consequences:
1. **Query performance:** `read_events(work_item_id)` reads all events for a work-item. At 10K events, this is slow even with indexing.
2. **Replay time:** `replay()` rebuilds projection from the full event log. Factory's 16-day missions would take minutes to replay.
3. **Storage cost:** Postgres JSONB is not compact. 10K events × 2KB each = 20MB per work-item. 100 work-items = 2GB. This is small today but grows linearly.

## Position

**Define a retention policy with hot/cold tiering: recent events in Postgres, archived events in compressed JSONL files, replay supports reading from both tiers.**

### Proposed policy

1. **Hot tier:** Events younger than 30 days or belonging to work-items in non-terminal states (`new`, `in_progress`, `gating`). Stored in `events` table (Postgres JSONB).

2. **Cold tier:** Events older than 30 days for work-items in terminal states (`locked`, `cannot_proceed`). Archived to `.factory/archive/events/<work_item_id>/<year>-<month>.jsonl.gz`.

3. **Access pattern:**
   - `read_events()` checks hot tier first; if work-item is terminal and events are missing, falls back to cold tier
   - `replay()` loads hot events, then appends cold events in sequence
   - `query_work_items()` only queries hot projection (`work_items_current`)

4. **Compaction trigger:** Nightly job or manual `sub.archive_events(older_than=timedelta(days=30))`.

### Why not just DELETE old events

Events are the authoritative log. Deleting them breaks replay, audit, and telemetry. Compression + cold storage preserves bytes without sacrificing the append-only invariant.

### Minimal alternative

If cold tiering is too complex, start with **event compaction within Postgres**:
- For terminal work-items, collapse sequences of `heartbeat_claim` events into a single "heartbeat summary" event
- Collapse `poll_hooks` no-op events
- This reduces event count without losing semantic state

## Risks

| Risk | Mitigation |
|---|---|
| Cold tier files are lost or corrupted | Store SHA-256 of each archive file in Postgres; validate on read |
| Replay across hot+cold boundary is slow | Pre-sort cold events by `event_seq`; read only needed ranges |
| Principal cannot verify archive integrity | Archive includes a manifest file with event counts and hashes; human-readable |
| Compression adds dependency | Use `gzip` from Python standard library; no external packages |

## Blocking

Not blocking any current phase. This is infrastructure debt that becomes load-bearing when:
- A single project exceeds 1,000 work-items
- A mission runs longer than 7 days
- Replay time exceeds 30 seconds

These thresholds should be measured and tracked. When any is breached, this debate becomes an active breadcrumb.

## Next step

1. Add telemetry metric: `event_count_per_work_item` and `replay_duration_ms`
2. Run a stress test: insert 10,000 events for one work-item, measure `read_events` and `replay` latency
3. Set thresholds: if `replay > 30s` or `events > 10K`, auto-file a breadcrumb
4. Keep this debate open until thresholds are measured
