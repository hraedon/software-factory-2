---
number: "211"
title: "No Prometheus metrics endpoint despite spec §7 claiming one"
severity: medium
status: proposed
kind: improvement
author: adversarial-review
date: "2026-05-25"
tags: [observability, telemetry, phase-6]
related: ["BC-210"]
---

## Problem

Spec §7 states: "Outcome dashboard for the principal: per-spec status, per-stage timing, escalations, dead-letters. Built on regista's event store + Prometheus metrics." The codebase has zero Prometheus integration. `telemetry.py` is a CLI tool that prints tables, not a metrics endpoint.

The "fleet health monitor" described in spec §7 (per-channel uptime, rate-limit hits, average latency) also does not exist.

## Impact

Without metrics, the factory cannot be monitored by standard infrastructure tooling (Grafana, Datadog, etc.). Per-channel latency and rate-limit data exists only in structured logs, not queryable metrics.

## Proposed fix

Add a `factory.metrics` module that exposes a Prometheus-compatible `/metrics` endpoint. Key metrics:
- `sf2_work_items_total{state, type}` — work item state gauge
- `sf2_gate_duration_seconds{gate_name, outcome}` — gate evaluation latency
- `sf2_channel_invocations_total{channel, model, outcome}` — channel usage
- `sf2_pipeline_duration_seconds{project_name}` — end-to-end pipeline time
