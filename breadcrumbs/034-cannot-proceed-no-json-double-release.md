---
number: "034"
title: "Cannot_proceed without diagnostics file causes double-release — fixed with channel_fail fallback"
severity: high
status: resolved
kind: bug
author: opencode
date: "2026-05-07"
tags: [runner, bug]
related: ["019", "021"]
---

## Problem

In `runner.py:_handle_invoke_failure`, when a channel returns `error_message="cannot_proceed"` but no `cannot_proceed.json` file exists in the attempt directory, the code fell through to `release_claim(work_item_id, actor_id)`. But the claim had already been released by the earlier `transition("claim")` call — `release_claim` raised `CLAIM_NOT_FOUND`.

## Resolution

Changed the else branch to `transition("channel_fail", ...)` with diagnostic payload `"cannot_proceed without diagnostics file"`, matching the same fallback path used for other channel failures. This releases the claim via the state transition and records the event for telemetry.