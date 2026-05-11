---
number: "094"
title: Tests write to hardcoded /tmp paths
description: >
  test_gate_assertion_count.py used Path("/tmp/test_...") for all test files.
  Parallel pytest workers or concurrent runs collide on the same paths, causing
  flaky failures and potential cross-test contamination.
severity: medium
status: resolved
kind: bug
author: opencode-adversarial-review
date: "2026-05-11"
tags: [tests, hygiene, flakiness]
---

## Resolution

Replaced all hardcoded /tmp paths with the `tmp_path` pytest fixture parameter.

## Files changed

- `tests/test_gate_assertion_count.py`
