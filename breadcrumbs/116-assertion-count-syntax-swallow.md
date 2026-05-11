---
number: "116"
title: _check_assertion_count returns passed=True on SyntaxError
description: >
  The assertion-count gate catches SyntaxError and returns passed=True, skipping
  the check entirely. While syntax is checked earlier in evaluate_test_suite, this
  is a defense-in-depth gap: a later mutation or a direct caller of
  _check_assertion_count would silently skip assertion validation on invalid code.
severity: medium
status: proposed
kind: bug
author: opencode-adversarial-review
date: "2026-05-11"
tags: [gate, test_suite, assertion-count, silent-correctness]
---

## Proposed fix

Return passed=False with a syntax diagnostic, or raise/return an explicit
invalid-artifact result that upstream callers can map to a syntax gate failure.

## Affected file

- `src/factory/gate.py`
