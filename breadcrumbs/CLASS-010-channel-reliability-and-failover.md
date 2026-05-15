---
number: "CLASS-010"
title: "Channel Reliability and Failover"
severity: critical
status: active
kind: defect-class
author: rfc-016-backfill
date: "2026-05-15"
tags: [channel, failover, reliability]
related: ["019", "044", "109", "135", "136", "149", "150", "RFC-006"]
---

## Shape

A model channel returns empty output, times out, errors, or is unavailable, and the pipeline either retries indefinitely, deadlocks on backoff, or silently proceeds with no output.

## Systemic cause

Model channels are external services with unreliable availability. Resilience mechanisms were added incrementally rather than designed as a coherent layer, leading to interactions between backoff/failover/budget that produce deadlocks.

## Systemic fix

BC-136 failover + BC-150 backoff fix + BC-149 pre-flight model ping. The three mechanisms together form a coherent resilience layer. Monitoring for new interaction bugs.

## Trigger condition

≥5 instances (current: 8). Systemic fix deployed.

## Instances

| BC   | Symptom |
|------|---------|
| 019  | Channel failure modes untested |
| 044  | OpenCodeChannel mutates self._family on invoke() — race condition |
| 109  | No circuit breaker or backoff for failing channels |
| 135  | glm-5.1 returns empty output for implementer role |
| 136  | Channel failover — automatic backup channel |
| 149  | Model availability regression — DeepSeek and GLM both dead |
| 150  | Channel backoff creates permanent deadlock |
| RFC-006 | Per-project venv isolation for subprocess gates |