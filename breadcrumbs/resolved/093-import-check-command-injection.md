---
number: "093"
title: Command injection in pre_gate import smoke check
description: >
  _run_import_check in pre_gate.py interpolated artifact_path.stem directly into
  `python -c "import {module_stem}"`. Today the stem is system-controlled, but the
  function has no guard to enforce it is a valid Python identifier. A caller
  passing a user-influenced filename would create an immediate python -c injection.
severity: high
status: resolved
kind: bug
author: opencode-adversarial-review
date: "2026-05-11"
tags: [pre_gate, security, command-injection, stage-4]
---

## Resolution

Added `str.isidentifier()` validation before constructing the import statement.
Invalid module names now return an explicit failure dictionary.

## Files changed

- `src/factory/pre_gate.py` — `_run_import_check` module name validation
