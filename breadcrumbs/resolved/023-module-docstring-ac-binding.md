---
number: "023"
title: "Structural semantics gate rejected module-level AC docstrings"
severity: high
status: implemented
kind: bug
author: test-audit
date: "2026-05-07"
tags: [gate, stage-5, tests]
resolution: extended-module-docstring-support
---

## Background

The structural-semantic check `_check_structural_semantics` only looked at function and class docstrings when binding AC references. A `.pyi` file that satisfied an AC via a module-level docstring:

```python
"""Satisfies AC-01."""
def foo(x: int) -> str: ...
```

would fail the gate with "AC 'AC-01' not in any function/class docstring — detached from contract", even though the AC is clearly present and bound to the module contract.

## Discovery

This was discovered during BC-016 resolution: after removing the substring check, the gate_process integration test `test_gate_passes_valid_artifact` failed because its test artifact used a module docstring for the AC reference.

## Fix applied (2026-05-07)

Extended `_check_structural_semantics` to also scan `ast.get_docstring(tree, clean=False)` (the module docstring) for AC references. Module-level refs are recorded against a sentinel name `"<module>"`. This preserves the existing function/class binding behavior while allowing module-level prose.

Updated the test artifact in `test_gate_process.py` to use a module docstring, confirming the fix.
