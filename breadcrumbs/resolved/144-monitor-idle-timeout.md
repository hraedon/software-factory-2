---
number: "144"
title: "agent_golden_run.py idle timeout too aggressive — killed working pipeline"
severity: medium
status: implemented
kind: bug
author: agent
date: "2026-05-14"
tags: [process, golden-run, agent-safety]
related: ["140"]
---

## Summary

The monitor's idle detection (`max_idle_cycles=3`, 3 × interval) declared processes idle when the runner was silently processing a model call. Each model invocation + inner gate retries can take 2–5 minutes. With a 60s monitor interval, 3 cycles = 180s, which is shorter than a single long model call.

## Root cause

The idle detection assumed that no new log lines means the pipeline is finished. But the runner produces no intermediate log lines during a blocking subprocess call (opencode invocation). The only log events are claim_acquired and the result (submit or channel_fail), with a gap of 2–5 minutes in between.

## Resolution

Increased `max_idle_cycles` from 3 to 10 (10 × 60s = 10 minutes before declaring idle). Also increased `claim_near_budget` fatal threshold from 3 to 5 to account for multiple budget-exhausted items without killing the run.
