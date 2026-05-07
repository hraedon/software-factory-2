---
number: "021"
title: "Non-cannot_proceed channel failures produce no substrate event for telemetry"
severity: high
status: implemented
kind: design
author: test-audit
date: "2026-05-07"
tags: [runner, telemetry, stage-1, failure-routing]
related: ["019"]
resolution: added-channel_fail-event
---

## Background

When a channel invocation fails with a non-cannot_proceed error (timeout, non-zero exit, empty output, extraction failure), `_handle_invoke_failure` at `runner.py:204-243` logs the error via structlog and calls `sub.release_claim()`. It does NOT write a substrate event.

This means:
- No `event` entry records the failure for telemetry or retry budget tracking.
- `derive_failures()` in `failure_summary.py` only looks at `gate_fail` events — channel invocation failures are invisible to it.
- The `attempt_threshold` warning in `worker_loop` (lines 87-93) fires based on `claim.attempt_number`, but there is no structured record of *why* the attempt failed.

## Why this matters

Phase 2 will have per-role per-channel pass-rate telemetry (spec §7). If channel failures are not captured as events, the pass-rate reporter will undercount failures and overestimate reliability. A role with frequent timeouts will look better than it is.

## Resolution (2026-05-07)

Added `sub.append_event()` call inside `_handle_invoke_failure` for non-cannot_proceed failures. The event uses:
- `transition="channel_fail"`
- `payload["diagnostics"] = {"error_message", "timed_out", "exit_code"}`
- `actor_metadata` with role/channel/family/attempt_n/context_hash

Added `append_event` method to `MockSubstrate` to support testing.

Updated channel failure tests (`test_channel_failures.py`) to assert that a `channel_fail` event is recorded with correct diagnostics and actor metadata.

This is Option 1 (write a `channel_fail` event) without adding a new workflow transition — `append_event` creates an event that does not transition state, preserving the existing behavior where the item stays in `in_progress` and becomes reclaimable after TTL expiry.

