---
number: "058"
title: "Stage handoff and diagnostic dispatch are parallel truth to FactoryConfig"
severity: medium
status: proposed
kind: design
author: session
date: "2026-05-08"
tags: [config, runner, scheduler, router]
related: ["056"]
---

## Problem

BC-056 centralized all identifier strings into `factory/constants.py`, but two structural dictionaries remain as hand-maintained parallel truth alongside `FactoryConfig`:

1. **`scheduler._STAGE_HANDOFF`** maps `(work_item_type, state) → {next_type, link_type, additional_links, next_role}`. The `next_role` and `next_type` fields duplicate `FactoryConfig.PHASE2_TYPE_TO_ROLE`. The `link_type` and `additional_links` fields are pipeline topology that has no config representation. When Phase 3 adds new roles (cross-family reviewer, frontier judge), both `_STAGE_HANDOFF` and `PHASE2_TYPE_TO_ROLE` must be updated in lockstep — a coordination hazard.

2. **`router._PHASE2_DISPATCH`** maps `DiagnosticKind → Route(target_state, target_role)`. The `target_role` fields duplicate role names already in `PHASE2_TYPE_TO_ROLE`. The routing logic (which diagnostic kind routes to which role and state) is pipeline-specific, but the role names should come from config, not be re-typed as bare constants.

Both dictionaries encode pipeline topology that will change when Phase 3 adds roles. Currently they are correct-by-inspection but not correct-by-construction.

## Fix

Derive `_STAGE_HANDOFF` from `FactoryConfig` plus a new `stage_topology` config section that declares `link_type` and `state` per transition edge. The scheduler would call `config.stage_handoff_for(type, state)` instead of indexing a module-level dict.

For `_PHASE2_DISPATCH`, add a `diagnostic_routing` config section (or YAML) that maps `DiagnosticKind → (target_state, target_type)` and derive `target_role` from the type-to-role mapping already in config.

Both changes defer to Phase 3 when multi-role topology actually changes. For Phase 2 (three roles, single channel), the current hardcoded dicts are correct and test-covered.