---
number: "114"
title: pre_gate _run_ruff_fast mutates artifact file in-place
description: >
  The inner gate runs `ruff check --fix` on the original artifact path, then
  `ruff format`. The file on disk is modified. If the subsequent pytest gate
  fails and the runner retries, the model receives a modified file in its retry
  prompt context.
severity: medium
status: resolved
kind: bug
author: opencode-adversarial-review
date: "2026-05-11"
tags: [pre_gate, side-effect, inner-gate]
---

## Proposed fix

Copy the artifact to a temp directory before running `ruff check --fix` and
`ruff format`, leaving the original untouched. This is already done for mypy and
pytest; ruff should follow the same pattern.

## Affected file

- `src/factory/pre_gate.py`

## Resolution

Both `_run_ruff` (gate.py) and `_run_ruff_fast` (pre_gate.py) now copy the artifact to a tempdir before running `ruff --fix`, leaving the original untouched.
