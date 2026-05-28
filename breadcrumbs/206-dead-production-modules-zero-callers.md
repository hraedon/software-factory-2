---
number: "206"
title: Dead production modules with zero callers (~1300 lines)
severity: medium
status: resolved
kind: improvement
author: adversarial-review
date: "2026-05-25"
tags: [dead-code, maintenance, CLASS-014]
related: ["197"]
---

## Problem

Six modules under `src/factory/` are imported only by their own test files and never called from production code paths:

| Module | Lines | Description |
|---|---|---|
| `state_reporter.py` | 346 | Pipeline state snapshot (RFC-018) |
| `bundler.py` | 289 | Artifact bundling (RFC-019) |
| `spec_hash.py` | 69 | Spec mutation detection (RFC-021) |
| `prompt_audit.py` | 389 | Prompt conflict detection (RFC-001) |
| `ops/` package | ~200 | Resource limits, disk monitoring, log rotation (RFC-017) |

Combined, these represent ~1,300 lines of dead code that accumulate maintenance burden and inflate vulture whitelist entries.

Additionally, two functions are dead:
- `render_decomposer_prompt()` in `context.py` — superseded by Phase B decomposer
- `format_summarized_failures()` in `failure_summarizer.py` — never called

## Context

These modules were built for planned Phase 6+ features. They have test coverage but no production integration. The `render_decomposer_prompt` function was removed in the current session's adversarial review.

## Fix

Removed all 5 dead modules and their test files:
- `src/factory/state_reporter.py` + `tests/test_state_reporter.py`
- `src/factory/bundler.py` + `tests/test_bundler.py`
- `src/factory/spec_hash.py` + `tests/test_spec_hash.py`
- `src/factory/prompt_audit.py` + `tests/test_prompt_audit.py`
- `src/factory/ops/` (entire package) + `tests/test_ops.py`

Also removed dead `build_summarizer_prompt()` function from `failure_summarizer.py` + its tests in `tests/test_failure_summarizer.py`.

**Net reduction**: ~1,300 lines of production code + ~72 test cases removed.

The modules can be re-added when their RFCs are prioritized and have production integration points. The RFCs (RFC-001, RFC-017, RFC-018, RFC-019, RFC-021) remain in the breadcrumbs as design proposals.
