---
number: "109"
title: No circuit breaker or backoff for failing channels
description: >
  If a channel is consistently returning non-zero exit codes (rate-limited, auth
  expired, binary missing), the runner retries every poll_interval_seconds (5s by
  default), claiming work items and immediately failing them. This wastes substrate
  claims and pollutes the event log with identical channel_fail transitions.
severity: medium
status: proposed
kind: design
author: opencode-adversarial-review
date: "2026-05-11"
tags: [runner, channel, resilience, circuit-breaker]
---

## Proposed fix

Add a per-channel failure counter with exponential backoff (e.g., after 3
consecutive channel_fails, increase effective poll interval to 30s, 60s, 120s).
Reset counter on a successful submit.

## Affected file

- `src/factory/runner.py`
