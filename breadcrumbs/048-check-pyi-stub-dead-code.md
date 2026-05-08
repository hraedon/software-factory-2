---
number: "048"
title: "_check_pyi_stub SyntaxError handler is dead code"
severity: low
status: proposed
kind: bug
author: adversarial-review
date: "2026-05-08"
tags: [gate, stage-2]
related: []

---

## Problem

`gate.py:90-91`:

```python
    except SyntaxError:
        pass
```

`_check_pyi_stub` calls `ast.parse(content)` at line 70. If the content has a `SyntaxError`, the `except SyntaxError: pass` handler runs and returns the fallthrough `GateResult(passed=True)` at line 92.

But `evaluate_interface_spec` calls `_check_syntax` first (line 37), which also calls `ast.parse` and returns `GateResult(passed=False)` on `SyntaxError`. If the content has a syntax error, `_check_pyi_stub` is never reached. The `SyntaxError` catch in `_check_pyi_stub` is unreachable dead code.

## Fix

Remove the `try/except SyntaxError: pass` block. If a defensive guard is desired, it should at minimum return `GateResult(passed=False)` rather than silently passing.
