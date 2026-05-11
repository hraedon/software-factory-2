---
number: "105"
title: ast.parse on arbitrary user code is a DoS vector
description: >
  The gate layer calls ast.parse on model-generated code with no size limit.
  Python's ast.parse can consume significant memory on a huge file, and combined
  with the lack of artifact size limits (BC-095, BC-104), this is a direct DoS
  vector against the gate process.
severity: medium
status: proposed
kind: bug
author: opencode-adversarial-review
date: "2026-05-11"
tags: [gate, DoS, ast, resource-exhaustion]
related: ["095", "104"]
---

## Proposed fix

Size guard first (BC-104) is the primary defense. Secondary: consider using
`compile()` with a timeout or memory limit, or run ast.parse in a subprocess
with a capped input size.

## Affected files

- `src/factory/gate.py`
- `src/factory/pre_gate.py`
