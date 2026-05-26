---
number: "216"
title: "Spec review stage — model-mediated architectural review before decomposition"
severity: high
status: implemented
kind: improvement
author: adversarial-review
date: "2026-05-26"
tags: [decomposer, spec-review, composition, phase-6]
related: ["209", "RFC-023"]
---

## Problem

The factory pipeline had no pre-pipeline architectural review of specs. The socratic-specification process has composition checks (Step 5), but they were advisory — the AI could skip them under context pressure. The cert-watch one-shot implementation hit the same gaps the factory did: orphaned definitions (scheduler, validate_chain_order, delete), missing runtime context (AlertConfig), and write-only data paths (scan_history). These gaps are cheap to catch before implementation and expensive to catch after.

## Fix

Two-layer composition defense:

### Layer 1: Model-mediated spec review (`src/factory/spec_review.py`)

Runs before decomposition. A model reviews the spec from an architect's perspective, checking six patterns:
1. Orphaned definitions (function defined, no AC calls it)
2. Missing runtime context (configurable dataclass, no stated source)
3. Write-only data paths (data written, no stated consumer)
4. Missing lifecycle hooks (background behavior, no AC places it in runtime)
5. Underspecified error propagation (function can fail, no stated error path)
6. Dependency inversions or missing prerequisites

Each finding includes an `inferred_answer` and `confidence` score (0-1). Findings with confidence >= threshold (default 0.7) are auto-resolved and recorded. Low-confidence findings are surfaced to the principal.

Usage:
```
python -m factory.spec_review --spec tests/fixtures/cert-watch/spec.md --threshold 0.7
```

Or integrated into populate:
```
python populate_work_items.py --spec-yaml spec.yaml --spec-review --decomposer-channel opencode
```

### Layer 2: Mechanical composition gate (Phase B.5 in `decomposer_model.py`)

After Phase B produces a decomposition, a structural check flags modules that have dependencies but no inbound references (orphaned leaf modules). This is a warning, not a failure — it signals that the module may need a wiring AC.

### Socratic-specification changes

- Removed cross-model audit requirement from process.md Step 5 (the factory's spec_review.py provides the cross-model backstop for factory-bound specs; standalone socratic-spec use doesn't need it)
- Made composition checks blocking for MVP scope (gaps must be resolved before synthesis, not just noted)

## Tests

28 tests in `test_spec_review.py` covering JSON parsing, prompt building, finding classification, auto-resolve/surfaced split, channel failure handling, and CLI output formatting. All 52 existing decomposer tests continue to pass.
