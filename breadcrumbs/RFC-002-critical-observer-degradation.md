---
number: "RFC-002"
title: "Critical observer degradation — v1 BC-359 shows silent swallowing loses telemetry data"
severity: high
status: proposed
kind: design
author: adversarial-review
date: "2026-05-08"
tags: [telemetry, hooks, dep-v1-359]
related: ["033", "044"]
---

## Problem

v1's BC-359: `ObserverBus.fire()` caught all exceptions from every observer and logged warnings. RunRecorderObserver failing silently dropped run history. MemoryGraphObserver failing silently dropped decisions. The operator saw green exit code but had incomplete data.

v2 will have observers/hooks that fire on pipeline events (work-item transitions, gate results, escalations). These observers drive the telemetry that Principles 10 and 11 depend on for model placement. A silent observer failure that drops telemetry data could cause:
- Wrong model promoted to a load-bearing role based on incomplete pass-rate data.
- Budget-wasting retries because failure patterns weren't recorded.
- Principal operating without accurate outcome data.

## Proposal

Design v2's observer/hook system with explicit degradation semantics from day one:
1. Each observer declares `is_critical: bool`.
2. Critical observer failure → degraded exit code (e.g., `ExitCode.OBSERVER_DEGRADED`), pipeline continues but reports degradation.
3. Non-critical observer failure → logged warning, no exit code change.
4. At pipeline end, a `DegradationReport` lists every observer that failed, how many events it missed, and the impact.

## Dependencies

Awaits Phase 3+ when v2 has multiple hooks/observers. The design decision should be made before implementing the first observer — retrofitting is what created v1's BC-359.
