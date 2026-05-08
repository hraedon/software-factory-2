---
number: "057"
title: "Dead code audit — no CI enforcement for unused code accumulation"
severity: low
status: resolved
kind: improvement
author: adversarial-review
date: "2026-05-08"
tags: [ci, gate, testing]
related: []
---

## Problem

v1 accumulated backward-compat shims, unused imports, and orphaned test fixtures because there was no recurring dead-code audit. BC-048 and BC-053 were resolved by removing the dead code they identified, but there is no automated guard preventing recurrence.

Without an automated check, dead code survives indefinitely because no human reviews the factory's own code.

## Fix

Add a dead-code detection step to `make check` (or a new `make audit` target):
1. `vulture src/ tests/` — finds unused code with low false-positive rate.
2. Or a simpler regex-based check for `def ...(...)` without callers (acceptable for a project this size).

Set the threshold at zero: any detected dead code fails CI. This forces resolution (delete or document intended use) rather than accumulation.

## Resolution

Removed dead code found by initial audit: `KIND_TO_ROLE` dict (router.py), `work_root()` function (workspace.py), redundant `invocation_family` reassignment (claude_code_channel.py). Added `vulture>=2.0` to dev dependencies, `make audit` target, and included in `make check`. Whitelist at `.vulture_whitelist.py` for signal handler `frame` params. 282 tests pass.
