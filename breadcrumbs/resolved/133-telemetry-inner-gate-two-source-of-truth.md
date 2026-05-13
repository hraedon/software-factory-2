---
number: "133"
title: Telemetry two-source-of-truth — inner-gate signal lives only in runner logs
severity: high
status: implemented
kind: improvement
author: agent
date: "2026-05-13"
tags: [telemetry, runner, gate, stage-3, stage-4]
related: ["075", "086", "RFC-002", "RFC-018"]
---

## Problem

Inner-gate pass/fail signals existed only in runner structlog output. The telemetry module (`telemetry.py`) explicitly filtered out inner-gate gate names (`if not a.gate_name.startswith("inner_")`) and the exit criteria report included a caveat: "inner-gate retry data requires runner-log parsing; not captured in substrate events."

This meant the inner-gate first-attempt pass rate (74% in GR-021) could only be extracted from runner logs via `scripts/work_item_size_metrics.py`, not from substrate. Two separate data sources for pipeline health metrics.

## Fix

### SubmitPayload extended with `inner_gate_attempts`

`event_schemas.py`: `SubmitPayload` now carries an optional `inner_gate_attempts: list[dict] | None` field. Each entry has `retry`, `gate_name`, `passed`, and `diagnostics` keys.

### Runner collects and emits inner gate history

`runner.py`: `_inner_gate_loop()` now returns a 4-tuple including `list[dict]` of all inner gate attempt results (initial check + each retry). `process_work_item()` passes this list into the submit transition payload. Non-inner-gate roles (reviewer, judge) emit `None`.

### Telemetry reads inner gate attempts from substrate

`telemetry.py`: `collect_gate_attempts()` now extracts inner gate attempts from submit event payloads and creates `GateAttempt` records for each. `ExitCriteriaMetrics` has three new fields: `inner_gate_first_pass_rate`, `inner_gate_first_passes`, `inner_gate_evaluations`. The exit criteria summary now reports inner gate first-pass rate as a separate line. The "Phase 3" label was also corrected to "Pipeline".

## Validation

- 608 tests pass, 13 skipped, 0 lint errors
- New test `test_inner_gate_attempts_extracted_from_submit_payload` verifies end-to-end extraction
- Pre-existing tests unaffected (SubmitPayload.from_dict backward-compatible)
