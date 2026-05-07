---
number: "016"
title: "AC reference check uses substring search — false positives likely"
severity: medium
status: proposed
kind: design
author: test-audit
date: "2026-05-07"
tags: [gate, stage-5]
---

## Background

`_check_ac_references` at `gate.py:95-106` uses `ac_id not in content` — a raw Python substring check. This means:

- An AC ID mentioned only in a comment like `# AC-02 was removed` would pass.
- An AC ID inside a string literal like `msg = "AC-02 failed"` would pass.
- Partial prefix matches could create false positives (e.g., `AC-0` matching `AC-01`).

The structural-semantic check (`_check_structural_semantics`) mitigates this slightly by requiring AC references in function/class docstrings, but the raw substring check in `_check_ac_references` remains the gate that runs when `ac_ids` are provided without `TS-` prefixes.

## Options

1. **Remove `_check_ac_references` entirely** — rely on `_check_structural_semantics` which already checks that each AC is bound to a docstring. The substring check is then redundant.
2. **Tighten `_check_ac_references`** to only match AC patterns in docstrings or comments with specific syntax (e.g., `re.search(r'"""[^"]*AC-01', content)`).
3. **Leave as-is** — the current double-check (substring + structural) provides defense in depth, and false positives from comments are unlikely with Claude's output patterns.

## Acceptance criteria

- Decision recorded on which option to pursue.
- If option 1: remove `_check_ac_references`, update `evaluate_interface_spec`, update tests.