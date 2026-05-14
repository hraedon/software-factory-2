---
number: "143"
title: "claim_near_budget releases claim without terminal transition — zombie items cycle forever"
severity: high
status: implemented
kind: bug
author: agent
date: "2026-05-14"
tags: [runner, failure-routing]
related: ["139", "055"]
---

## Summary

When `claim.attempt_number >= attempt_threshold`, the runner released the claim (`sub.release_claim`) but did not transition the item to a terminal state. The item returned to `new` state and was immediately reclaimed by the runner, creating an endless claim→release→claim→release cycle.

## Root cause

The BC-139 fix added `claim_near_budget` as a runner-level hard stop to prevent budget burn. However, releasing a claim only returns the item to `new` — it doesn't prevent re-claiming. The BC-139 router-level escalation (gate_fail → cannot_proceed_seam at threshold) only fires after a gate evaluation, but the runner skips gate processing for budget-exhausted items.

## Impact

Items at attempt threshold cycled forever: claim → release → claim → release. Each cycle acquired and released a claim (fast, ~5ms), producing hundreds of `claim_near_budget` log warnings. No model budget was burned (the runner skips invocation), but the item was stuck in a perpetual loop.

## Resolution

`claim_near_budget` now performs two transitions:
1. `claim` (new → in_progress)
2. `cannot_proceed` (in_progress → cannot_proceed, terminal)

This properly terminates budget-exhausted items. Validated in GR-027: 4 items escalated to `cannot_proceed` with no cycling.
