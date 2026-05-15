---
number: "146"
title: "test_suite_assertions gate false-negative on pytest.raises / pytest.warns / unittest assertions"
severity: medium
status: implemented
kind: bug
author: agent
date: "2026-05-14"
tags: [gate, false-negative]
related: []
---

## Summary

The `test_suite_assertions` gate's `_count_asserts` (in `src/factory/gate.py`) only counted `ast.Assert` nodes. Tests using idiomatic pytest exception/warning matchers — `with pytest.raises(...):` or `with pytest.warns(...):` — and `unittest.TestCase.assert*` method calls were read as zero-assertion functions and rejected with `test_no_assertions`.

Surfaced in GR-027 item `16ee8dac` (test_suite). The artifact had 7 test functions and 13 actual checks; one function used `with pytest.raises(AttributeError): summary.hostname = "other"` to verify frozen-dataclass immutability, the canonical pytest idiom. The gate flagged it as zero-assertion and the item escalated to `cannot_proceed`.

## Root cause

`_count_asserts` walked the AST counting only `ast.Assert`. It missed:

- `with pytest.raises(...):` / `with pytest.warns(...):` (and the `match=` variants) — `ast.With` items whose `context_expr` is a `Call` to a `pytest.raises|warns` attribute or bare name.
- `pytest.raises(...)` used as a bare callable (e.g. `pytest.raises(ValueError, fn, arg)`).
- `unittest.TestCase.assert*` and `assertRaises*` method calls (`self.assertEqual(...)`, `self.assertRaises(...)`, etc.).

## Resolution

Updated `_count_asserts` to additionally count:

1. `ast.With` items whose `context_expr` is a `Call` whose function resolves to `pytest.raises`, `pytest.warns`, `raises`, or `warns`.
2. Direct `Call` nodes to the same set of names (covers non-`with` usage and `pytest.raises` used as a function).
3. `Call` nodes whose function is an `Attribute` access starting with `assert` (covers `self.assertEqual`, `self.assertRaises`, etc.).

Added test coverage in `tests/test_gate_assertion_count.py`.
