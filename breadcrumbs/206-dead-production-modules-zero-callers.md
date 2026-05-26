---
number: "206"
title: Dead production modules with zero callers (~1300 lines)
severity: medium
status: in_progress
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

## Partial fix (Session 53)

Added Phase 6 feature-flag docstrings to all five modules (`state_reporter.py`, `bundler.py`, `spec_hash.py`, `prompt_audit.py`, `ops/__init__.py`) documenting RFC number, integration trigger, and BC tracking. This makes the dead-code status discoverable without removing the code.

## Remaining

Either integrate these modules into production paths (per their RFCs) or remove them. The docstring markers are a stopgap — they don't reduce maintenance burden, only make it visible.
