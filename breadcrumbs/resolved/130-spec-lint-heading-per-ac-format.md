---
number: "130"
title: "spec_lint only handled bulleted AC format — heading-per-AC specs were all ERROR"
severity: medium
status: resolved
kind: bug
author: glm-5.1
date: "2026-05-12"
tags: [spec, lint, phase-3]
related: ["127"]
---

## Problem

`spec_lint.py` only supported `## Acceptance Criteria` sections with `- AC-NN:` bullet items. The real cert-watch fixture specs use `## AC-NN: Title` heading-per-AC format, which caused every spec to fail with `ERROR [ac_section_exists] No '## Acceptance Criteria' section found`.

Additionally, the `_extract_acs` heading-per-AC parser had a dead-code expression on line 74 (`current_id is not None` as a bare expression instead of an assignment) and a redundant `continue` on line 79 that could never be reached.

## Fix

Refactored `_extract_ac_section` + `_parse_ac_bullets` into a unified `_extract_acs()` that handles both formats:

1. If `## AC-NN:` headings are found, parse heading-per-AC (title line + body text until next heading).
2. Otherwise, fall back to `## Acceptance Criteria` section with bulleted items.

All 8 cert-watch specs now lint correctly (0 errors, 5 warnings). 7 new tests for heading-per-AC format. 557 total tests pass.

## Validation

- `spec_lint` on cert-watch fixtures: 0 errors, 5 warnings (1 AC count over cap, 4 single-concern)
- `spec_lint` on cert-watch-mini fixtures: 0 errors, 1 warning (1 AC count)
- Deterministic output verified (two runs produce byte-identical results)
- `populate_work_items.py --strict-lint` exits non-zero on warnings
- `--skip-lint` bypass works