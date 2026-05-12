---
number: "125"
title: "populate_work_items.py --config doesn't infer --workflow from config YAML"
severity: medium
status: proposed
kind: bug
author: opencode-session-25
date: "2026-05-12"
tags: [populate, golden-run, config]
related: []
---

## Problem

When `--config` is provided, `populate_work_items.py` overrides `--dsn`, `--project`, `--key-path`, and `--workspace-root` from the config YAML. However, `--workflow` (which determines `workflow_version` and the registered workflow file) is NOT inferred from the config's `workflow_version` field. It defaults to `phase2` regardless.

This caused GR-019's first attempt to populate work items with `workflow_version=2` while the config specified `workflow_version: 3`. The runner queried for `workflow_version=3` and found zero items.

## Impact

Golden runs that use `--config` with a phase3 workflow will silently create work items in the wrong workflow version. The runner sits idle, finding no claimable items.

## Affected file

- `populate_work_items.py` lines 228-234: `workflow_version` derived from `args.workflow` only, ignoring config.

## Proposed fix

When `--config` is provided and `args.workflow` was not explicitly set, infer the workflow from `config.workflow_version`:

```python
if config is not None and args.workflow == parser.get_default("workflow"):
    if config.workflow_version == 1:
        args.workflow = "phase1"
    elif config.workflow_version == 3:
        args.workflow = "phase3"
```

## Workaround

Pass `--workflow phase3` explicitly alongside `--config`.
