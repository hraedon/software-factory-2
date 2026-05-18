---
number: "183"
title: "unsupported_import_pattern classifier produces false-positive feedback for stdlib/third-party submodule imports"
severity: medium
status: implemented
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

## Fix

Implemented option 1 (whitelist/suppression approach) in `src/factory/pre_gate.py`:

- Added `_parse_requirements_packages(requirements_path)` — parses a
  requirements.txt and returns a normalised `frozenset[str]` of top-level
  package names (lower-case, dashes→underscores, version specifiers stripped).

- Added `_is_safe_from_feedback(top_level, known_packages)` — returns `True`
  when a top-level module name is stdlib (via `sys.stdlib_module_names`) or
  appears in the caller-supplied known_packages set.

- Modified `_parse_import_failure` to accept `known_packages: frozenset[str]`
  and, in both the dotted-submodule and wrong-module-name branches, fall back
  to `_IMPORT_FEEDBACK_KIND_OTHER` when the failing module's top-level package
  is safe.  This suppresses the misleading feedback without affecting the import
  check failure itself.

- Modified `_run_import_check` to accept `requirements_path: Path | None`,
  parse it via `_parse_requirements_packages`, and pass the result into
  `_parse_import_failure` as `known_packages`.

- Modified `pre_gate_interface_spec` to accept and thread `requirements_path`.

- Modified `_run_pre_gate` in `runner.py` to pass
  `config.workspace_root / "requirements.txt"` when it exists.

## Touched surface

- `src/factory/pre_gate.py` — two new helpers, `_parse_import_failure`
  signature extended, `_run_import_check` and `pre_gate_interface_spec`
  signatures extended.
- `src/factory/runner.py` — `_run_pre_gate` threads `requirements_path` to
  `pre_gate_interface_spec`.
- `tests/test_import_feedback.py` — 22 new tests in 5 new classes covering
  AC-1 through AC-4 plus helpers.  One existing test's example updated from
  `os.path` (stdlib, now correctly suppressed) to `cryptography.hazmat`
  (non-stdlib, correctly classified as dotted_submodule).

## Test results

956 passed, 13 skipped, 0 failed across full test suite.

## Severity rationale

Medium. False-positive import feedback doesn't crash the pipeline, but it
actively harms model retry quality by telling the model to "fix" imports
that are already correct. This contributes to inner-gate exhaustion cycles
(2 of 3 exhausted items in GR-036 had incorrect feedback on every retry).
Not high because the model sometimes recovers on its own (1 item recovered
after `dotted_submodule` feedback on retry 0).
