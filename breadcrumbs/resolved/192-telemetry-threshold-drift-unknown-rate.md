---
number: "192"
title: "Telemetry verify and pass-rate formatter use different unknown-rate thresholds"
severity: low
status: implemented
kind: bug
author: claude
date: "2026-05-18"
tags: [telemetry, thresholds, BC-068-followup]
related: []
---

# BC-192 — `run_telemetry_verify` (<1%) and `format_pass_rate_table` (<=10%) disagree

## Problem

In `src/factory/telemetry.py`, `run_telemetry_verify` blocks at `unknown_count == 0` and `unknown_rate < 0.01`. `format_pass_rate_table` accepts up to `0.10`. The thresholds for "trustworthy" diverge by 10x between the gate that decides "telemetry is good enough to publish" and the formatter that humans read.

BC-068 (resolved) closed the structural "unknown" issue by making `gate_name` flow through the manifest. The fallback paths (`role=worker_meta.get("role", "unknown")`, `gate_name = GATE_NAME_UNKNOWN`) are still present at `telemetry.py:311-315, 343-358` and used. Whichever path produces "unknown" today is not the issue — the issue is that two callers can look at the same dataset and reach opposite "is this OK?" conclusions.

## Proposed fix

Define a single constant `TELEMETRY_UNKNOWN_RATE_THRESHOLD` and use it in both `run_telemetry_verify` and `format_pass_rate_table`. Decide the value:

- **Strict (0.01):** any non-zero unknown is treated as suspect when the formatter runs. Forces operators to fix data quality before reading the table.
- **Permissive (0.10):** verify also relaxes. Allows partial-data reads during pipeline build-out.

Recommend strict (0.01) for the post-Phase-2 state — adversarial review of placement decisions depends on it.

## Acceptance criteria

1. One constant; both call sites import it.
2. Test asserts the constant is used in both paths.
3. Documentation note in `spec.md` §10 references the threshold.

## Resolution

Added `TELEMETRY_UNKNOWN_RATE_THRESHOLD = 0.01` to `constants.py`. Both `format_pass_rate_table` (was 0.10) and `run_telemetry_verify` (was 0.01 inline) now use the constant. Label updated from `[target: <=10%]` to `[target: <1%]`. Test added verifying the constant is imported and used.
