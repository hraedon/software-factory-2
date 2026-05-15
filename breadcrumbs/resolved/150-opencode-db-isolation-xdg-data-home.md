---
number: "150"
title: "Isolate opencode session DB per golden run via XDG_DATA_HOME"
severity: medium
status: implemented
kind: improvement
author: agent
date: "2026-05-15"
tags: [opencode, golden-run, agent-mediated, data-isolation]
related: ["140", "141"]
---

## Summary

`opencode run` persists every invocation into `~/.local/share/opencode/opencode.db`. There is no `--no-save` or `--stateless` flag. Factory golden runs invoked via `agent_golden_run.py` were cluttering the principal's persistent DB with hundreds of sessions (452 sessions / 11,612 messages / 49,486 parts = 336 MB at time of investigation).

## Fix

`scripts/agent_golden_run.py` now:

1. Creates a temp directory per run: `/tmp/sf2-golden-grNNN-opencode-data`
2. Injects it as `XDG_DATA_HOME` into the environment of runner, gate, and scheduler subprocesses
3. `opencode run` writes its session DB there instead of `~/.local/share/opencode/`
4. Cleans up the isolated DB after the run (preserved with `--no-cleanup`)

## Verification

- `python3 -c` test confirmed `opencode` respects `XDG_DATA_HOME`
- GR-029 executed with `XDG_DATA_HOME=/tmp/sf2-golden-gr029-opencode-data`
- Telemetry confirmed the isolated DB was written and removed
- `tests/test_agent_golden_run.py` — new test `test_cleanup_removes_isolated_opencode_db` passes

## Documentation

`AGENTS.md` updated:
- Workspace isolation section now mentions XDG_DATA_HOME isolation
- Cleanup step now lists the isolated opencode DB dir
- Preserved wording: principal's persistent store is never touched
