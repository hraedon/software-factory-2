---
number: "168"
title: "Phase 5 link types had reversed source/target direction — scheduler create_link failed for integrates and verified_by"
severity: high
status: resolved
kind: bug
author: glm-5.1
date: "2026-05-15"
tags: [scheduler, stage-8, stage-9, integration, outcome-verification, dep-v1]
related: ["058", "132", "148"]
---

## Problem

The scheduler creates links with `from=downstream(new_item), to=source(locked_item)`, following the convention that `link_type` matches `source_type→target_type` where `source` is the newly created item. But `workflows/phase5.yaml` defined the two new Phase 5 link types with reversed direction:

- `integrates: source_type=jury, target_type=integration` (should be `source_type=integration, target_type=jury`)
- `verified_by: source_type=integration, target_type=outcome_verification` (should be `source_type=outcome_verification, target_type=integration`)

Additionally, `golden-run-029-config.yaml` and `golden-run-030-config.yaml` used `link_type: derived_from` for jury→integration handoffs, which doesn't exist in the workflow link_types.

This caused `SubstrateError: Link type 'derived_from' not allowed between 'integration' and 'jury'` when the scheduler tried to create integration items downstream of locked juries, blocking the entire Phase 5 chain from completing.

## Impact

- GR-029: scheduler crashed (exit code 1), outcome_verification never created
- GR-030 (first attempt): same link_type error, integration items never created
- Any Phase 5 golden run would fail at the jury→integration handoff

## Fix

1. Reversed source/target in `workflows/phase5.yaml`:
   - `integrates: source_type=integration, target_type=jury`
   - `verified_by: source_type=outcome_verification, target_type=integration`
2. Changed `golden-run-030-config.yaml` stage_topology:
   - `jury→integration: link_type: integrates` (was `derived_from`)
   - `integration→outcome_verification: link_type: verified_by` (was `derived_from`)

## Validation

GR-030 (second attempt) successfully created integration work items downstream of locked juries, confirming the scheduler handoff chain works end-to-end.