---
number: "136"
title: Channel failover — automatic backup channel on empty output, API errors, and timeouts
severity: high
status: implemented
kind: improvement
author: principal
date: "2026-05-14"
tags: [runner, channel-opencode, channel-gemini, failure-routing, stage-4]
related: ["135", "109", "059"]
---

## Problem

When a channel fails (empty output, API error, timeout, rate limit), the pipeline records a `channel_fail` transition and re-queues the work item for another attempt on the same channel. There is no mechanism to fall back to an alternate channel/model. If a provider has a prolonged outage (as seen with z.ai in GR-024), the pipeline will exhaust its retry budget on a dead channel before succeeding.

## Evidence

- GR-024: 13/16 glm-5.1 attempts returned empty output (transient z.ai outage). Pipeline cycled through all 13 retries on the same channel before some eventually succeeded.
- GR-025: glm-5.1 as juror returned empty output on all 8 attempts, contributing to `jury_disagree`. A fallback to K2 would have produced a quorum.
- The empty-output retry (BC-135) handles transient blips (1 retry, 3s delay) but cannot recover from sustained provider outages.
- The channel backoff mechanism (30s→300s) prevents tight failure loops but also stalls the pipeline.

## Proposed design

### Per-role failover config

Extend `RoleConfig` with an optional `fallback_channel` and `fallback_model`:

```yaml
roles:
  - role: implementer
    channel: opencode
    model: zai-coding-plan/glm-5.1
    fallback_channel: opencode
    fallback_model: fireworks-ai/accounts/fireworks/routers/kimi-k2p6-turbo
```

### Failover triggers

On `InvocationResult(success=False)`, invoke the fallback if any of:
1. `error_message` contains "Empty output"
2. `timed_out` is True
3. `exit_code` is non-zero (API error)
4. `error_message` contains "not found in PATH" (channel binary missing)

### Failover semantics

- Failover is invoked immediately on the same work item attempt (no substrate round-trip).
- If the fallback also fails, the combined failure is recorded as a single `channel_fail` event.
- Telemetry records both the primary and fallback channel in the event payload.
- Inner gate retries use the fallback channel for subsequent attempts within the same inner gate loop.
- Jury jurors with fallback: if primary fails, fallback juror is invoked; the juror key reflects the channel that actually responded.

### Constraints

- Fallback is per-role, not global. Different roles can have different fallback channels.
- Only one level of fallback (no chaining). If the fallback fails, the attempt fails.
- Fallback channel must be registered in `_CHANNEL_CONSTRUCTORS`.

## Impact

- Pipeline resilience against provider outages (z.ai, Fireworks, Ollama)
- Multi-family jury becomes practically reliable: if one provider is down, the fallback provider contributes a vote
- No spec changes required — this is a runner-level concern
