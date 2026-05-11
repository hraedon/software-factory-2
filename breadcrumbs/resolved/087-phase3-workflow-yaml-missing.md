---
number: "087"
title: Phase 3 workflow YAML missing — FactoryConfig.phase3() sets version=3 but no matching workflow file exists
severity: high
status: implemented
kind: bug
author: opencode
date: "2026-05-11"
tags: [runner, stage-4, workflow]
related: []
---

## Description

`FactoryConfig.phase3()` sets `workflow_version=3`, but:

1. No `workflows/phase3.yaml` exists (only phase1.yaml v1 and phase2.yaml v2)
2. `populate_work_items.py` `--workflow` only accepts `["phase1", "phase2"]` — no phase3 option
3. `full_pipeline.yaml` is version 2, not 3
4. All 13 golden run configs use `workflow_version: 2`

The runner, scheduler, and gate_process query substrate work items filtered by `config.workflow_version`. If `phase3()` config is used, they'd query for version 3 while all work items are registered at version 2 — finding zero items. The pipeline would silently do nothing.

## Proposed fix

1. Create `workflows/phase3.yaml` (copy of phase2.yaml with version bumped to 3, or reference full_pipeline.yaml)
2. Add "phase3" to `populate_work_items.py` --workflow choices
3. Create `golden-run-015-config.yaml` using FactoryConfig.phase3() bindings
