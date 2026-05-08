---
number: "053"
title: "evaluate_deterministic_gates is dead code — defined but never called"
severity: low
status: proposed
kind: improvement
author: adversarial-review
date: "2026-05-08"
tags: [gate]
related: []

---

## Problem

`gate.py:548-594` defines `evaluate_deterministic_gates(artifact_files, config)` — a function that takes a dict of artifact paths and runs existence/empty/syntax checks on each. It is never called anywhere in the codebase:

```
$ rg evaluate_deterministic_gates src/ tests/
gate.py:548:def evaluate_deterministic_gates(
```

Only the definition site. The actual gate evaluation path goes through `evaluate_interface_spec`, `evaluate_test_suite`, and `evaluate_implementation` — all called individually from `gate_process.py`.

## Recommendation

Either remove the dead code or document its intended use. It might be a planned integration-stage gate (spec Stage 8) that was written but never wired in. If it has future value, add a comment noting which phase it's planned for.
