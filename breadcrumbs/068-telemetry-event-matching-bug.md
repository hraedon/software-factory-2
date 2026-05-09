---
number: "068"
title: "Telemetry reporter matches gate events with 'unknown' gate name and 0% first-attempt pass rate"
severity: high
status: proposed
kind: bug
author: opencode
date: "2026-05-09"
tags: [telemetry, runner, gate, dep-v1-NNN]
related: ["033", "044", "057"]
---

## Summary

Golden runs 004 and 005 both exhibited the same telemetry data-quality issue: the `collect_gate_attempts()` → `compute_pass_rates()` pipeline in `telemetry.py` produces rows with:
- `gate_name = "unknown"`
- `first_attempt_pass_rate = 0%`

for legitimate gate-pass events. This means the telemetry reporter cannot reliably distinguish which gate evaluated an artifact, and all pass-rate statistics are suspect.

The event-matching logic pairs `submit` events with subsequent `gate_pass`/`gate_fail` events by work_item_id. It derives `gate_name` from the gate event's actor_metadata or payload. When the pairing succeeds but the gate name extraction fails, it falls back to `"unknown"`.

## Impact

- **Fleet-placement decisions are data-blind.** Phase 3 role-to-channel binding depends on per-(role, channel, gate) pass rates. If gate names are unknown, the table collapses into a single bucket and cannot discriminate "mypy failures on K2" from "pytest failures on Claude."
- **Golden-run evaluation is misleading.** The 0% first-attempt rate suggests every item failed its first attempt, even when GR004/005 show 80–90% first-attempt success.
- **The bug is latent in unit tests.** `test_telemetry.py` exercises synthetic event streams but does not assert that real substrate event shapes (from `ActorMetadata.to_dict()` and gate payload structure) produce non-unknown gate names.

## Likely causes

1. **Payload shape drift.** `gate_process.py` writes diagnostics into both `payload={"diagnostics": ...}` and `custom_fields={"diagnostics": ...}`. The telemetry collector may be reading from the wrong field, or the gate name may not be present in the expected nested path.
2. **ActorMetadata missing gate_name.** The gate actor metadata carries `role`, `channel`, `family`, `attempt_n`, but not the specific gate that ran (e.g., `implementation_mypy`). The telemetry logic may be looking for a field that was never added.
3. **Event ordering / missing events.** If `gate_pass` events lack the expected payload (because `gate_process.py` only includes diagnostics on failure), the fallback `"unknown"` fires even on success paths.

## Proposed fix

1. Add `gate_name` to the gate actor metadata in `gate_process.py` so every gate event self-describes which gate evaluated the artifact.
2. Update `telemetry.collect_gate_attempts()` to read `gate_name` from actor_metadata first, then payload, then custom_fields, with explicit logging when none is found.
3. Add a telemetry data-quality test that replays a golden-run event subset and asserts zero `"unknown"` gate names and non-zero first-attempt pass rates.
4. Optionally: add a `telemetry --verify` CLI mode that reads the live substrate and reports data-quality stats (unknown-rate, orphan submit events, unmatched gate events).

## Related v1 lesson

v1 BC-359 (critical observer degradation) and BC-360 (telemetry event shape drift) both show that telemetry event schemas that are not versioned and validated in CI eventually produce silent data corruption. v2 should not repeat that pattern.
