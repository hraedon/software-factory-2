---
number: "002"
title: "Telemetry data quality — event-matching bug blocks fleet-placement decisions"
author: opencode
date: "2026-05-09"
related: ["BC-068", "BC-033", "RFC-002"]
---

## Context

Golden runs 004 and 005 both exhibited a telemetry data-quality issue: the `collect_gate_attempts()` → `compute_pass_rates()` pipeline produces rows with `gate_name = "unknown"` and `first_attempt_pass_rate = 0%` for legitimate gate-pass events. This was noted in the 2026-05-09 worklog entry but not yet fixed.

Telemetry is the empirical foundation for Phase 3 fleet integration. The spec §5 states: *"Per-role per-channel telemetry drives model placement... updated based on data, not vibes."* If the data is wrong, the placement is wrong.

## Problem

The telemetry reporter pairs `submit` events with subsequent `gate_pass`/`gate_fail` events by `work_item_id`. The `gate_name` is derived from the gate event's `actor_metadata` or `payload`. When pairing succeeds but name extraction fails, it falls back to `"unknown"`. The 0% first-attempt rate suggests the pairing logic is not correctly correlating first attempts with their gate outcomes.

The bug is latent — unit tests pass because they use synthetic event shapes that don't match real regista event shapes from golden runs.

## Position

**Fix telemetry event-matching before any Phase 3 work begins.** This is a data-quality prerequisite, not a feature.

Specifically:

1. **Add `gate_name` to gate actor metadata.** `gate_process.py` should include the evaluating gate name (e.g., `implementation_mypy`, `test_suite_collect`) in `ActorMetadata` so every gate event is self-describing.

2. **Update `telemetry.collect_gate_attempts()` to read `gate_name` from `actor_metadata` first, then `payload`, then `custom_fields`, with explicit logging when none is found.** The fallback to `"unknown"` should emit a warning and be test-visible.

3. **Add a data-quality test that replays golden-run event subsets.** Extract a small fixture from GR004/005 event logs (anonymized) and assert zero `"unknown"` gate names and non-zero first-attempt pass rates. This test is the canary for future event-shape drift.

4. **Add a `telemetry --verify` CLI mode.** Reads the live regista and reports stats: unknown-rate, orphan submit events, unmatched gate events. Run this after every golden run as a sanity check.

## Why this blocks Phase 3

Phase 3 adds K2, GLM, DeepSeek, Gemini channel adapters and collects telemetry on the same workload as Phase 2. If the telemetry table collapses gate names into `"unknown"`, you cannot discriminate:
- "K2 fails mypy but passes pytest" vs
- "Claude passes both"

The fleet-placement table becomes a single bucket per role/channel, and the data-driven binding decision is blind.

## Risks

| Risk | Mitigation |
|---|---|
| Adding `gate_name` to actor_metadata changes event shape | Backward-compatible: it's an additive field; existing events omit it and get `"unknown"` fallback |
| Golden-run event fixtures contain sensitive data | Anonymize: strip artifact paths, replace actor_ids with hashes, keep only event topology and transition names |
| Fixing this reveals other telemetry bugs | That's the point. Better to find them now than during fleet tuning |

## Next step

File a focused breadcrumb (or upgrade BC-068) with the four specific fixes above. Target: 1 session, 2–3 new tests, no Phase 3 work until telemetry `--verify` passes clean on a golden-run replay.
