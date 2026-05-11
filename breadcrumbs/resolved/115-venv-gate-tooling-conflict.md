---
number: "115"
title: ensure_project_venv installs gate tooling into project venv
description: >
  It always appends pytest, mypy, ruff to the install list. If the project's
  requirements.txt pins conflicting versions, the install may fail or produce an
  inconsistent environment.
severity: low
status: resolved
kind: bug
author: opencode-adversarial-review
date: "2026-05-11"
tags: [venv, gate-tooling, dependency-conflict]
---

## Proposed fix

Install gate tooling into a separate, isolated venv (e.g., `.venv-gate`) and use
that python executable for gates, while the project venv remains pure.

## Affected file

- `src/factory/venv.py`

## Resolution

Gate tooling (pytest, mypy, ruff) now installed in a separate `.venv-gate` directory, keeping the project venv pure and avoiding dependency conflicts.
