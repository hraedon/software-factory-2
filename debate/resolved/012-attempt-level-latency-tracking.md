---
number: "012"
title: "Attempt-level latency tracking — the missing dimension in fleet placement"
author: glm-5.1
date: "2026-05-09"
related: ["002", "011", "BC-033"]
---

## Context

Spec §7 states the telemetry reporter should produce: *"Per-role per-channel pass-rate reporter... producing the table that drives role-binding decisions. Format: `(role, channel) → first-attempt pass rate, mean attempts to pass, mean wall-clock, gate-failure breakdown`."*

The current implementation (`telemetry.py`) produces first-attempt pass rate and total pass rate. It does not produce mean wall-clock or gate-failure breakdown. The `GateAttempt` dataclass has no timing field.

GR004 (Claude Sonnet) took ~31 minutes. GR005 (Kimi k2.6) took ~52 minutes. The telemetry report shows pass rates but not that Sonnet was 40% faster. For fleet placement, a channel that passes 80% in 31 minutes may be strongly preferred over one that passes 87% in 52 minutes — but the data to make this tradeoff is invisible.

## Problem

Fleet placement without latency data optimizes for pass rate only. This produces sub-optimal bindings:

1. **Slow-but-accurate vs fast-but-good-enough.** If GLM passes 85% in 15 minutes and Claude passes 90% in 45 minutes, the implementer role (spec §5: "slot-filling, bulk") should use GLM, but the data only shows 85% vs 90%.

2. **Timeout calibration.** `timeout_seconds: int = 600` in `RoleConfig` is the same for all roles and all channels. But GR005 shows Kimi takes 68% longer than Sonnet. If the timeout is calibrated for Sonnet, Kimi may timeout on harder items. If calibrated for Kimi, Sonnet wastes time on stuck invocations. Per-channel latency data enables per-channel timeout calibration.

3. **Total mission time estimation.** The principal needs to know how long a mission will take. Without per-attempt latency data, mission time can only be estimated from wall-clock observation, not from telemetry.

## Position

**Add wall-clock duration per attempt to the telemetry pipeline.** Record invocation start and end times; include in telemetry grouping.

### Proposed design

1. **In the runner:** record `invocation_start_time` before `channel.invoke()` and `invocation_end_time` after. Store both in `actor_metadata` alongside the existing `channel`, `model`, `family`.

2. **In `GateAttempt`:** add `duration_seconds: float`. Computed from the submit event's `actor_metadata.invocation_end_time - invocation_start_time`.

3. **In `PassRateRow`:** add `mean_duration_seconds: float` and `median_duration_seconds: float`.

4. **In the report table:** add a "Mean Duration" column after "Pass Rate."

5. **In `FactoryConfig`:** add `per_channel_timeout: dict[str, int] | None = None` — optional per-channel timeout overrides. If present, overrides the global `timeout_seconds` for the named channel.

### Cost

~30 lines of code. No new dependencies. No changes to regista.

### Why this matters now

GR004 and GR005 are the first multi-channel data points. They show a 68% latency difference. Phase 3 will add 4 more channels with unknown latency profiles. Without latency tracking, the first fleet placement decision will optimize for pass rate only — a one-dimensional decision on a multi-dimensional problem.

## Risks

| Risk | Mitigation |
|---|---|
| Clock skew between invocation and gate evaluation | Use monotonic clock (`time.monotonic()`) for duration; wall-clock for display |
| Latency varies by spec complexity | Group by (role, channel) as today; normalize per work-item if needed |
| Per-channel timeout adds config complexity | Optional field; if absent, use global timeout (backward compatible) |

## Blocking

Phase 3 (fleet integration). Not strictly blocking — the fleet can be placed on pass rate alone — but the placement quality is materially worse without latency data.

## Next step

1. Add `invocation_start_time` / `invocation_end_time` to runner.py around `channel.invoke()`
2. Add `duration_seconds` to `GateAttempt` and `PassRateRow`
3. Update `format_pass_rate_table()` with duration column
4. Add `per_channel_timeout` to `FactoryConfig` (optional, backward compatible)
5. Two tests: synthetic events with timing → mean duration computed; missing timing → graceful fallback
