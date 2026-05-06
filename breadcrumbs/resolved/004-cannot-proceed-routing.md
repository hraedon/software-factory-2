---
number: "004"
title: "cannot_proceed routing has no workflow path"
severity: high
status: resolved
kind: bug
author: opencode
date: "2026-05-06"
tags: [runner, failure-routing, stage-2]
related: ["002"]
---

## Problem

When a channel returns `cannot_proceed` (structured failure per spec §6), the runner transitions the work-item with `submit` (`in_progress → gating`). The gate process then evaluates the item, finds no artifact on disk, and fails. The item loops back to `new` via `gate_fail`. This produces an infinite retry loop on genuinely ambiguous specs rather than routing to the spec-ambiguity resolver as the spec intends.

## Resolution

Added `cannot_proceed` terminal state and transition to both `phase1.yaml` and `full_pipeline.yaml`. The runner now transitions directly from `in_progress → cannot_proceed` (bypassing gating entirely) when a channel returns structured failure.

**Changes:**
- `workflows/phase1.yaml`: added `cannot_proceed` terminal state + transition from `in_progress`
- `workflows/full_pipeline.yaml`: same, with all roles in `allowed_roles`
- `src/factory/runner.py:_handle_invoke_failure`: uses `"cannot_proceed"` transition instead of `"submit"`
- `workflows/README.md`: updated state machine diagram and description

**Resolution note:** Phase 1 has no spec-ambiguity resolver role, so `cannot_proceed` is terminal. Phase 2+ should add a `cannot_proceed → in_progress` transition with the `spec_ambiguity_resolver` role to route items to the principal.
