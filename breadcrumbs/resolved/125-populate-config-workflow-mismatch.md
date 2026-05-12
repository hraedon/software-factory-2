---
number: "125"
title: "populate_work_items.py --config doesn't infer --workflow from config YAML"
severity: medium
status: resolved
kind: bug
author: opencode-session-25
date: "2026-05-12"
tags: [populate, golden-run, config]
related: []
---

## Problem

When `--config` is provided, `populate_work_items.py` overrides `--dsn`, `--project`, `--key-path`, and `--workspace-root` from the config YAML. However, `--workflow` (which determines `workflow_version` and the registered workflow file) is NOT inferred from the config's `workflow_version` field. It defaults to `phase2` regardless.

This caused GR-019's first attempt to populate work items with `workflow_version=2` while the config specified `workflow_version: 3`. The runner queried for `workflow_version=3` and found zero items.

## Resolution

`--workflow` default changed from `"phase2"` to `None`. When `--workflow` is not explicitly set:
1. If `--config` is provided, workflow is inferred from `config.workflow_version` via `{1: "phase1", 2: "phase2", 3: "phase3"}` mapping.
2. If `--config` is not provided, defaults to `"phase2"`.

Also fixed: summary line now prints the resolved `project` variable instead of `args.project`.
