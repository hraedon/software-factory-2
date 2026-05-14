---
number: "141"
title: "opencode run returns empty output when cwd is not a project directory"
severity: high
status: implemented
kind: bug
author: agent
date: "2026-05-14"
tags: [channel-opencode, runner, golden-run]
related: ["140", "040"]
---

## Summary

The `opencode run` subcommand silently returns empty stdout and stderr (exit code 0) when the subprocess working directory (`cwd`) is not a recognized opencode project directory. The factory's `SubprocessChannel.invoke()` used `cwd=str(outputs_dir)` which pointed to `/tmp/sf2-golden-NNN/<uuid>/attempt-NNNN/` — a path with no opencode project context.

## Root cause

Opencode resolves the project by walking up from cwd. When cwd is under `/tmp/` with no git repo or opencode config, it falls back to `projectID=global`. In this mode, `opencode run` processes the message (visible in opencode logs) but does not write the response to stdout.

## Impact

Every golden run executed via `scripts/agent_golden_run.py` (BC-140 wrapper) was broken because the wrapper launched processes from `/tmp`. GR-026 worked only because GLM launched from the repo root — the mistake BC-140 was designed to prevent.

## Resolution

1. Added `invocation_cwd: Path | None = None` to `FactoryConfig`.
2. `SubprocessChannel.invoke()` uses `config.invocation_cwd` (if set) as subprocess cwd, falling back to `outputs_dir`.
3. Golden run configs set `invocation_cwd: /projects/software-factory-2`.

Validated in GR-027: all model invocations produced non-empty output.
