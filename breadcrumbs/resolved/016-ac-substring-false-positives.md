---
number: "016"
title: "AC reference check uses substring search — false positives likely"
severity: medium
status: implemented
kind: design
author: test-audit
date: "2026-05-07"
tags: [gate, stage-5]
resolution: removed-redundant-check
---

## Background

`_check_ac_references` at `gate.py:95-106` uses `ac_id not in content` — a raw Python substring check. This means:

- An AC ID mentioned only in a comment like `# AC-02 was removed` would pass.
- An AC ID inside a string literal like `msg = "AC-02 failed"` would pass.
- Partial prefix matches could create false positives (e.g., `AC-0` matching `AC-01`).

The structural-semantic check (`_check_structural_semantics`) mitigates this slightly by requiring AC references in function/class docstrings, but the raw substring check in `_check_ac_references` remains the gate that runs when `ac_ids` are provided without `TS-` prefixes.

## Resolution (2026-05-07)

Removed `_check_ac_references` entirely. The structural-semantic check already enforces that every declared AC is bound to a function or class docstring (or module docstring). This is strictly stronger than a substring search:
- Comments and string literals no longer count.
- Partial prefix matches are impossible because we match whole words in docstrings.
- ACs are structurally attached to the contract, not merely present in the file.

Also extended `_check_structural_semantics` to honor module-level docstrings so that top-level prose (e.g. `"""Satisfies AC-01."""`) is valid.
