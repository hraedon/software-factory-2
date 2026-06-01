---
number: "220"
title: "Decomposer produces cross-workload contamination — hallucinated FR-05 with wrong-spec content"
severity: medium
status: implemented
kind: bug
author: opencode
date: "2026-05-28"
tags: [decomposer, phase-6, channel-claude]
related: ["RFC-023", "209"]
---

## Problem

When running the model-driven decomposer (Phase B) on `dep-graph-viewer/spec.yaml` via claude-code Sonnet, the decomposer produced 9 files instead of 4. Alongside the correct semantic-named files (`wi_event_log_reader.md`, `wi_graph_builder.md`, `wi_graph_filter.md`, `wi_dot_emitter.md`), it produced:

- `wi_fr01.md` through `wi_fr04.md` — Phase A fallback files with correct dep-graph-viewer content
- `wi_fr05.md` — **hallucinated FR-05 containing log-redact-cli content** (AC-LOG-08, AC-LOG-09, audit trail/redaction rule glossary terms)

The `wi_fr05.md` file has glossary entries for "audit entry", "redaction rule", "replacement type", "rule scope", and "structured log" — all from the log-redact-cli spec, not dep-graph-viewer. The dep-graph-viewer spec only has 4 FRs (FR-01 through FR-04).

## Root cause

The claude-code channel likely retained context from the prior log-redact-cli decomposition (GR-043), which was run in the same session or context window. When asked to decompose dep-graph-viewer, Sonnet mixed content from both specs.

## Impact

If populate runs against the full decomposer output directory, it creates work items for hallucinated FRs with wrong-spec content. These items will fail at the gate (wrong acceptance criteria) or, worse, produce code for the wrong workload. The contamination is caught by spec_lint (AC-LOG IDs don't match dep-graph-viewer's AC-DGV format), but the lint only warns on AC-format mismatches, it doesn't reject them.

## Proposed fix

1. The decomposer should only produce files matching the FR IDs declared in `spec.yaml`'s `functional_requirements` list. If the model produces extra FRs, they should be filtered out.
2. The Phase B decomposer should not produce Phase A fallback files alongside semantic-named files — it should produce one or the other, not both.
3. `populate_work_items.py` should validate that fixture FR IDs match the spec's declared FR IDs and reject fixtures with unknown FRs when `--strict-lint` is enabled.

## Workaround

Manually inspect decomposer output before populating. Use only the semantic-named files (Phase B) and discard all `wi_frNN.md` files.

## Fix

Added hallucinated FR ID gate to `_validate_decomposition()` in `decomposer_model.py`: when `spec_fr_ids` is provided (extracted from `spec.yaml`'s `functional_requirements`), any module claiming an FR ID not in the spec is rejected with `hallucinated_fr_id` diagnostic. The `decompose_from_model()` function extracts FR IDs from the spec YAML and passes them to validation. 3 new tests.
