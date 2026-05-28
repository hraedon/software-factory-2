---
number: "033"
title: "Telemetry reporter skeleton (Wave 8)"
severity: medium
status: resolved
kind: improvement
author: opencode
date: "2026-05-07"
tags: [telemetry, runner]
related: []
---

## Proposal

Extend `report.py` to produce per-(role, channel, gate) first-attempt pass-rate tables from regista event data. This establishes the baseline that Phase 3's channel additions will be measured against.

Spec §7: "Per-role per-channel telemetry drives model placement; no silent promotion."

## Implementation sketch

- `report.py` reads regista events via `read_events(actor_id=...)` grouped by role
- Computes first-attempt pass rate: items where the first `gate_pass` event has `attempt_n=1`
- Outputs markdown table to stdout
- CLI entry point: `factory-report`

## Dependencies

- BC-030 (composite `read_events`) would make this more efficient but is not blocking
- Wave 7 (golden-run-002) should land first to establish the baseline

## Resolution

Created `src/factory/telemetry.py` with `collect_gate_attempts()`, `compute_pass_rates()`, and `format_pass_rate_table()`. Groups by (worker_role, channel, family, gate_name) derived from submit→gate event pairing. Outputs first-attempt and overall pass-rate table. CLI entry point `factory-report` registered in pyproject.toml. 12 tests in `test_telemetry.py`. 282 total tests pass.