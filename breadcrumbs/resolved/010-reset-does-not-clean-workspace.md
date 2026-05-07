---
number: "010"
title: "populate_work_items.py --reset does not clean workspace"
severity: high
status: resolved
kind: bug
author: opcode-golden-run-001
date: "2026-05-07"
tags: [runner, stage-1, workspace]
related: ["003"]
---

## Background

`populate_work_items.py --reset` calls `drop_project_schema` to destroy the substrate project database schema, then creates a fresh project. But it does not clean `workspace_root`.

This means when the user does:

```bash
populate_work_items.py --reset --project sf2_golden_001
factory-run --config golden-run-001-config.yaml
```

The workspace under `/tmp/sf2-golden-001/` still contains attempt directories from the prior run. If any prior attempt directory matches a new work-item UUID (not possible since UUIDs are regenerated on reset), the runner would treat it as resumable and skip invocation.

Even when UUIDs differ, stale workspace directories accumulate across resets, consuming disk and creating confusion during post-mortem analysis (the golden run workspace had 61 files where 33 were expected).

## Impact

- Disk bloat across repeated `--reset` cycles.
- Confusion during post-mortem: artifacts from prior runs are indistinguishable from current-run artifacts without comparing UUIDs.
- Theoretical correctness hazard if UUID randomness ever collides (astronomically unlikely but architecturally untidy).

## Fix

Add `shutil.rmtree(workspace_root, ignore_errors=True)` to `_open_or_create_project` when `reset=True`, keyed on the config's `workspace_root`. The populate script needs access to the workspace_root path; add a `--workspace-root` argument defaulting to the config's value.

## Acceptance criteria

- Running `--reset` removes all contents of `workspace_root` before creating new work-items.
- A subsequent `--reset` run leaves exactly one attempt directory per work-item in the workspace (no accumulation).
