---
number: "070"
title: "Telemetry test helper _gate_md always emits payload on pass events — diverges from real gate_process shape"
severity: medium
status: resolved
kind: bug
author: opencode
date: "2026-05-09"
tags: [telemetry, testing, gate]
related: ["068"]
---

## Summary

The pre-BC-068 `_gate_md()` test helper in `test_telemetry.py` attached a `payload={"diagnostics": {...}}` dict to every gate event, including gate_pass events. In real `gate_process.py`, gate_pass transitions carry **no payload** — only `actor_metadata`. This made the telemetry bug invisible: the synthetic event shape always had `gate_name` in the payload, so the collector never hit the `"unknown"` fallback path that real events produced.

BC-068 fixed `_gate_md()` to match production (pass events now carry `None` payload, `gate_name` lives in `actor_metadata`). But the pattern is worth flagging: test helpers that fabricate regista event shapes should mirror the real event shapes that `gate_process.py` emits, not shapes that are convenient for the collector.

## Impact

- Any future bug where the collector relies on a payload field that the real gate process doesn't emit on pass events would again be hidden by the test helper.
- The broader risk is that any channel adapter or gate writer could silently drift from the test helper's shape, and telemetry tests would never catch it.

## Proposed improvement

Consider a `replay_from_real_events` integration test pattern: extract a small golden-run event subset from regista (or the golden-run fixtures) and assert that `collect_gate_attempts()` produces no `"unknown"` gate names and expected pass rates. This would close the shape-drift gap between synthetic tests and real event streams.