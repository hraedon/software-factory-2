---
number: "142"
title: "agent_golden_run.py launched processes from /tmp — broke opencode project context"
severity: high
status: implemented
kind: bug
author: agent
date: "2026-05-14"
tags: [process, runner, gate, golden-run, agent-safety]
related: ["140", "141"]
---

## Summary

The BC-140 wrapper script (`scripts/agent_golden_run.py`) launched runner/gate/scheduler processes with `cwd="/tmp"` for workspace isolation. This broke opencode's project context detection (BC-141), causing all model invocations to return empty output.

## Root cause

The script was designed to prevent opencode session DB pollution by isolating the process cwd from the repo root. However, workspace isolation is already handled by the config YAML's `workspace_root` field — the process cwd is irrelevant for artifact output. The opencode channel needs the repo root cwd to resolve its project context.

## Resolution

Changed `_launch_processes()` to use `cwd=REPO_ROOT` instead of `cwd="/tmp"`. Also added `git init` in the workspace directory as a safety measure.
