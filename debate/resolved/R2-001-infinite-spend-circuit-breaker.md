---
number: "R2-001"
title: "The 'Infinite Spend' Circuit Breaker (Budget Enforcement)"
author: gemini-cli
date: "2026-05-09"
related: []
---

## Context
In an event-driven system like Substrate with automatic retries, cross-family reviews, and behavioral gates, a logical bug can trap agents in a retry loop. V1 had a "Global Budget Breaker."

## Problem
If v2 operates for days (as the transcript suggests), a stuck multi-agent loop on K2 or Claude Opus could burn hundreds of dollars over a weekend. There is no debate addressing global token or financial budget constraints.

## Position
**Implement a strict, state-machine-level `budget_exhausted` transition that hard-halts the pipeline.**

### Proposed design
1. Track token usage and estimated cost per work-item and globally across the mission.
2. Introduce a `FactoryConfig` setting for `max_mission_budget` and `max_work_item_retries`.
3. If the budget is exceeded, the scheduler must force transition all active items to `cannot_proceed` with a specific escalation reason.