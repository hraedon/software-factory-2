---
number: "089"
title: ".pyi stub gate allows docstring-only bodies"
description: >
  _check_pyi_stub in gate.py accepted any ast.Constant (including docstrings) as a
  valid stub body. A function whose body consisted solely of a docstring passed the
  stub gate despite containing no Ellipsis, violating the spec that interface specs
  must use '...' as body.
severity: high
status: resolved
kind: bug
author: opencode-adversarial-review
date: "2026-05-11"
tags: [gate, interface_spec, stub, structural-semantics, stage-2]
related: ["013"]
---

## Resolution

Rewrote `_check_pyi_stub` to explicitly require `ast.Constant(value=...)` (Ellipsis)
or `ast.Pass` as the only permitted body statements. Docstrings alone no longer pass.

## Files changed

- `src/factory/gate.py` — `_check_pyi_stub` body validation
