---
number: "119"
title: "Venv gate tool hash won't detect version changes — only covers tool name list"
severity: low
status: proposed
kind: improvement
author: glm-5-1
date: "2026-05-11"
tags: [gate, venv, testing]
related: ["115"]
---

## Problem

The `.venv-gate/.gate_hash` is computed from `",".join(["pytest", "mypy", "ruff"])`, a static string. If a new version of pytest or mypy is released and the factory pins a different version, the hash won't change and the stale venv won't be rebuilt.

The existing `_clean_stale_project_venv` removes gate tools from the project venv but the replacement `.venv-gate` won't pick up version changes.

## Affected files

- `src/factory/venv.py` — `_gate_tools_hash()` and `_ensure_gate_venv`

## Proposed fix

Include pinned versions (from requirements or from `pip show` output) in the hash, or use a requirements file for gate tools instead of a hardcoded list.