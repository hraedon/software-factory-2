---
number: "091"
title: Relative imports bypass forbidden-module checks
description: >
  _import_module_name returned "" for relative ImportFrom nodes with no explicit
  module (e.g., `from . import conftest`). Since "" was not in any forbidden list,
  test suites and implementations could smuggle imports from conftest, pytest,
  implementation, src, or _impl via relative imports.
severity: high
status: resolved
kind: bug
author: opencode-adversarial-review
date: "2026-05-11"
tags: [gate, import-check, security, stage-5]
related: ["025"]
---

## Resolution

Modified `_import_module_name` to fall back to the first alias name when
`node.module` is empty/None, capturing `from . import conftest` and similar
relative imports.

## Files changed

- `src/factory/gate.py` — `_import_module_name` relative-import fallback
