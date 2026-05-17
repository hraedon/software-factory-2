---
number: "183"
title: "unsupported_import_pattern classifier produces false-positive feedback for stdlib/third-party submodule imports"
severity: medium
status: proposed
kind: bug
author: opencode
date: "2026-05-17"
tags: [gate, inner-gate, import-feedback, model-feedback, phase5]
related: ["173"]
---

## Symptom

In GR-036, the inner gate's import feedback classifier produced `wrong_module_name`
and `dotted_submodule` feedback for legitimate Python imports that work in the
real project venv but fail in the gate's synthetic flat-module environment:

- `from fastapi import FastAPI` → `wrong_module_name` (fastapi not in flat modules)
- `from unittest.mock import MagicMock` → `dotted_submodule` (stdlib submodule)
- `from fastapi.testclient import TestClient` → `dotted_submodule` (third-party submodule)
- `from collections.abc import Mapping` → `dotted_submodule` (stdlib submodule)

Two of the three `inner_gate_exhausted_retries` implementation items (3d029e6d,
9c324cd5) received `wrong_module_name` or `dotted_submodule` feedback on every
retry attempt. The feedback was incorrect (the imports work in the real venv)
but the model couldn't fix it because the gate's synthetic environment is
inherently different from the real one.

4 of 5 `inner_gate_exhausted_retries` cases received
`import_feedback_kind=wrong_module_name` despite the imports being correct for
the real project.

## Root cause

The gate's import check runs `python -c "import {module}"` in a synthetic
environment where dependencies are injected as flat `.py`/`.pyi` files. This
environment has no access to `site-packages` or stdlib submodules. When the
import fails, `_parse_import_failure()` classifies it as `wrong_module_name`
or `dotted_submodule`, and this feedback is injected into the model's retry
context via `render_prompt()`.

The classifier cannot distinguish between:
- A genuinely wrong import (e.g., `from certifcate_model import ...` with a typo)
- A correctly-spelled import that only fails in the synthetic env (e.g., stdlib submodules)

## Proposed fix

Two options:

1. **Whitelist approach**: Add known-safe import patterns (stdlib submodules,
   top-level third-party packages that are in the project's `requirements.txt`)
   to the import classifier. When an import matches a whitelist entry, mark it
   as `other_traceback` instead of `wrong_module_name` or `dotted_submodule`,
   and suppress the feedback.

2. **Environment enrichment**: Install the project's `requirements.txt` into
   the gate venv so that imports like `from fastapi import FastAPI` resolve.
   This partially defeats the isolation goal but eliminates the most common
   false positives.

Option 1 is less invasive. The key whitelist entries would be:
- `collections.abc.*`
- `unittest.mock`
- `unittest.*`
- Any package listed in `requirements.txt` that produces `wrong_module_name`

## Acceptance criteria

- AC-1: `from collections.abc import Mapping` does not produce
  `dotted_submodule` feedback.
- AC-2: `from unittest.mock import MagicMock` does not produce
  `dotted_submodule` feedback.
- AC-3: Third-party packages in `requirements.txt` (e.g., `fastapi`) do not
  produce `wrong_module_name` feedback.
- AC-4: Genuinely wrong imports (typos, non-existent modules) still produce
  `wrong_module_name` feedback.

## Severity rationale

Medium. False-positive import feedback doesn't crash the pipeline, but it
actively harms model retry quality by telling the model to "fix" imports
that are already correct. This contributes to inner-gate exhaustion cycles
(2 of 3 exhausted items in GR-036 had incorrect feedback on every retry).
Not high because the model sometimes recovers on its own (1 item recovered
after `dotted_submodule` feedback on retry 0).
