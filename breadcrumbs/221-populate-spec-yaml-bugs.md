---
number: "221"
title: "populate_work_items.py --spec-yaml mode has 3 bugs: workspace_root fallback, reset destroys decomposed files, requirements.txt not copied"
severity: high
status: implemented
kind: bug
author: opencode (mimo-v2.5-pro)
date: "2026-05-29"
tags: [populate, stage-1, decomposer]
related: ["219"]
resolved_date: "2026-05-29"
---

## Symptom

`populate_work_items.py --spec-yaml --decomposer-channel` mode fails to create work items when `--reset` is also used. The decomposer output is either written to the wrong directory or destroyed by the reset before populate can read it.

## Root cause

Three bugs in the `--spec-yaml` code path:

1. **workspace_root fallback** (line 385, 448, 471): `args.workspace_root` is `None` when not passed on CLI. The code used `args.workspace_root or "/tmp"` instead of the resolved `workspace_root` variable (which falls back to `config.workspace_root`). Decomposed files went to `/tmp/.decomposed` instead of the configured workspace.

2. **Reset destroys decomposed files**: The decompose step writes to `workspace_root / ".decomposed"` BEFORE `_open_or_create_project()` runs with `--reset`. The reset calls `shutil.rmtree(workspace)`, deleting the decomposed output. The populate loop then finds 0 files.

3. **requirements.txt not copied**: The `--spec-yaml` path doesn't set `fixtures_dir_custom`, so the `requirements.txt` copy (line 504-511) is skipped. The gate venv lacks project dependencies (e.g., `types-psycopg2`), causing mypy failures on modules that import external packages.

## Fix

All three bugs fixed:
- Bug 1: Use resolved `workspace_root` variable instead of `args.workspace_root`.
- Bug 2: Decompose to a temp directory (`tempfile.mkdtemp`), build items list from temp, then copy into workspace after reset.
- Bug 3: When `--spec-yaml` or `--spec-md` is used, derive the fixture directory from the spec file's parent and copy `requirements.txt` from it to the workspace root.

## Impact

This bug blocked every `--spec-yaml` golden run that also used `--reset`. GR-043 succeeded because it happened to work around the issue (the decomposed files were in `/tmp/.decomposed` from a prior run). GR-046 was the first run to hit all three bugs in sequence.

## Why this isn't the previous fix recurring

N/A — first instance of this defect shape. Related to BC-219 (hardcoded AC IDs) which is a different bug in the same code path.
