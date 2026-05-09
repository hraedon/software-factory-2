---
number: "066"
title: "cannot_proceed string overloaded as both state name and transition name"
severity: low
status: resolved
kind: improvement
author: adversarial-reviewer
date: "2026-05-08"
tags: [runner, gate, stage-4, stage-6]
related: []
---

## Summary

`STATE_CANNOT_PROCEED = "cannot_proceed"` and `TRANSITION_CANNOT_PROCEED = "cannot_proceed"` had identical string values. Any code comparing against the raw string `"cannot_proceed"` could not distinguish "the item is in this state" from "this transition just happened."

## Fix

Renamed `TRANSITION_CANNOT_PROCEED` to `TRANSITION_ROUTE_TO_CANNOT_PROCEED` to describe what happens (routing to the terminal state). The string value remains `"cannot_proceed"` for substrate protocol compatibility.