---
number: "210"
title: "No streaming/incremental telemetry — operators have no visibility during long runs"
severity: medium
status: proposed
kind: improvement
author: adversarial-review
date: "2026-05-25"
tags: [telemetry, observability, phase-6]
related: ["BC-033", "RFC-018"]
---

## Problem

The current telemetry runs after the pipeline completes (`factory.telemetry --config`). For long-running golden runs (~1h40m for GR-038), operators have no visibility into progress without manually tailing log files. The `agent_golden_run.py` wrapper prints status every 30s, but this is crude (line counts, not semantic progress).

The spec describes an "outcome dashboard" and "fleet health monitor" (spec §7) but neither exists. The state_reporter module (RFC-018) was implemented but is dead code (BC-206).

## Impact

Operators cannot detect stalled pipelines, budget exhaustion, or model degradation until the run completes. This wastes wall-clock time and makes debugging golden runs a forensic exercise rather than a real-time activity.

## Proposed fix

A lightweight substrate event subscriber that prints a one-line status update every N events (e.g., "12/34 items locked, 2 cannot_proceed, 3 in_progress, 17 new"). This could be:
1. A `--watch` mode on the existing telemetry CLI
2. A separate `factory.monitor` module that subscribes to substrate events
3. Integration with the state_reporter module (un-dead-code it)
