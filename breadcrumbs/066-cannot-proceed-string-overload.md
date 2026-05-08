---
number: "066"
title: "cannot_proceed string overloaded as both state name and transition name"
severity: low
status: proposed
kind: improvement
author: adversarial-reviewer
date: "2026-05-08"
tags: [runner, gate, stage-4, stage-6]
related: []

## Summary

`STATE_CANNOT_PROCEED = "cannot_proceed"` and `TRANSITION_CANNOT_PROCEED = "cannot_proceed"` have identical string values. Any code comparing against the raw string `"cannot_proceed"` cannot distinguish "the item is in this state" from "this transition just happened."

Currently no code appears to make this mistake — `route()` takes both `current_state` and `transition` as separate parameters, and gate process uses the enum constants. But it's a trap for future work: someone reading `if state == "cannot_proceed"` cannot tell which concept is being tested.

## Fix

Rename one to avoid collision. Options:
- `TRANSITION_CANNOT_PROCEED` → `TRANSITION_ROUTE_TO_CANNOT_PROCEED` (describes what happens)
- `TRANSITION_CANNOT_PROCEED` → `TRANSITION_TERMINAL` (describes result)
- `STATE_CANNOT_PROCEED` → `STATE_DEAD_LETTER` (matches spec §6 terminology: "dead-letter for unrecoverable")

Low priority — no active bug, just a readability trap. Should be decided before Phase 4 jury/disagreement routing adds more states and transitions.
