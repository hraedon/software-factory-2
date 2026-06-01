---
number: "219"
title: "spec_lint AC regex rejects AC-{PREFIX}-NN format; populate_work_items hardcodes ac_ids to AC-01"
severity: high
status: resolved
kind: bug
author: agent
date: "2026-05-28"
tags: [decomposer, spec-lint, populate, phase-6]
related: ["RFC-023", "209"]
---

## Problem

Two related bugs prevented the model-driven decomposer from working on specs with non-standard AC IDs:

1. **spec_lint.py AC regex too narrow.** The `_extract_acs()` regex `AC-\d+` only matches `AC-01`, `AC-02`, etc. Specs using prefixed AC IDs like `AC-LOG-01`, `AC-DGV-01` produce zero extracted ACs, causing `check_ac_section_exists` to report ERROR. The heading pattern also required a colon (`:`) that the decomposer's `_render_module_spec` doesn't emit.

2. **populate_work_items.py hardcodes `["AC-01"]`.** All four decomposer/fixtures code paths set `ac_ids` to `["AC-01"]` instead of extracting actual AC IDs from the fixture content. When the model reads a spec with `AC-LOG-01` but the work item's `ac_ids` field says `AC-01`, it correctly returns `cannot_proceed` because the IDs don't match.

**Impact:** GR-041 (K2 Phase B) had 3 `cannot_proceed` items out of 5 — all caused by the `ac_ids` mismatch. The model was blamed for ignoring the Phase B prompt, but the real root cause was the hardcoded AC IDs.

## Fix

1. **spec_lint.py** — Updated all AC regex patterns from `AC-\d+` to `AC-(?:[A-Z]+-)?\d+`. Made colon optional in heading pattern (`:?\s*`). All 29 spec_lint tests pass.

2. **populate_work_items.py** — Added `_extract_ac_ids_from_fixture()` helper that parses AC IDs from fixture file headings (both `## AC-01:` and `## AC-LOG-01` formats). Replaced all four hardcoded `["AC-01"]` instances with calls to this helper, falling back to `["AC-01"]` if no ACs found.

3. **decomposer_model.py** — Added AC condition text enrichment: when spec_data is available, AC entries are enriched with `condition` text from the spec's `acceptance_criteria` section. Also added FR-ID → semantic module_name mapping for dependency resolution so that dependency references use semantic names instead of FR IDs.

## Verification

- 81 decomposer/lint tests pass (29 spec_lint + 31 decomposer_model + 21 decomposer)
- 1107 full test suite passes
- GR-043: 97% lock rate (33/34) with MiMo-V2.5-Pro Phase B decomposition on log-redact-cli
