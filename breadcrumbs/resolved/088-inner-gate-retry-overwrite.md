---
number: "088"
title: Inner gate retry overwrites original artifact in-place
description: >
  _inner_gate_loop in runner.py invoked the channel into the same attempt directory
  as the original artifact, causing the channel output to overwrite the prior attempt
  before write_artifact created a manifest. A crash between channel completion and
  manifest write left a corrupt attempt with no recoverable state.
severity: critical
status: resolved
kind: bug
author: opencode-adversarial-review
date: "2026-05-11"
tags: [runner, inner-gate, data-loss, stage-4]
related: ["075"]
---

## Resolution

Changed `_inner_gate_loop` to invoke retries into a subdirectory `ad/retry-{N}`.
The original artifact at `ad/artifact.py` is preserved. On success, the retry
artifact is returned to `process_work_item`, which copies it to the canonical
location via `write_artifact`. On failure or crash, the original remains intact.

## Files changed

- `src/factory/runner.py` — `_inner_gate_loop` retry directory logic
