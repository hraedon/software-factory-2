---
number: "092"
title: SyntaxError swallowed in gate import checks
description: >
  Both the test-suite import gate (evaluate_test_suite) and the implementation
  import gate (_check_impl_imports) wrapped ast.parse in try/except SyntaxError:
  pass. A second, later syntax error in the file silently caused the import gate
  to return passed=True, letting malformed artifacts through.
severity: high
status: resolved
kind: bug
author: opencode-adversarial-review
date: "2026-05-11"
tags: [gate, syntax, silent-correctness, stage-5]
related: ["025"]
---

## Resolution

Replaced `except SyntaxError: pass` with explicit failure GateResults carrying
syntax diagnostics in both gates.

## Files changed

- `src/factory/gate.py` — `evaluate_test_suite` import check, `_check_impl_imports`
