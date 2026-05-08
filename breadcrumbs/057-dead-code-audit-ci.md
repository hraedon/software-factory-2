---
number: "057"
title: "Dead code audit — evaluate_deterministic_gates and _check_pyi_stub exist without CI enforcement"
severity: low
status: proposed
kind: improvement
author: adversarial-review
date: "2026-05-08"
tags: [ci, gate, testing]
related: ["048", "053"]
---

## Problem

v1 accumulated backward-compat shims, unused imports, and orphaned test fixtures because there was no recurring dead-code audit. The same pattern is starting in v2:

- `gate.py:548-594`: `evaluate_deterministic_gates()` — defined, never called (BC-053).
- `gate.py:90-91`: `except SyntaxError: pass` — unreachable (BC-048).

These are low-severity now but set a precedent. Without an automated check, dead code survives indefinitely because no human reviews the factory's own code.

## Fix

Add a dead-code detection step to `make check` (or a new `make audit` target):
1. `vulture src/ tests/` — finds unused code with low false-positive rate.
2. Or a simpler regex-based check for `def ...(...)` without callers (acceptable for a project this size).

Set the threshold at zero: any detected dead code fails CI. This forces resolution (delete or document intended use) rather than accumulation.
