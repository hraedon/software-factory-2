---
number: "104"
title: Gate layer reads artifacts without size limits
description: >
  The MAX_ARTIFACT_SIZE_BYTES constant added in BC-095 guards runner ingestion and
  channel stdout capture, but the gate and pre_gate modules still call
  artifact_path.read_bytes() / read_text() without any size check. An oversized
  artifact that reaches gating can still OOM the gate process.
severity: medium
status: proposed
kind: bug
author: opencode-adversarial-review
date: "2026-05-11"
tags: [gate, DoS, resource-exhaustion]
related: ["095"]
---

## Proposed fix

Add a shared `guard_artifact_size(path: Path) -> None` helper that raises a
SizeExceededError, and call it at the top of every gate evaluate_* function and
pre_gate function.

## Affected files

- `src/factory/gate.py`
- `src/factory/pre_gate.py`
