---
number: "206"
title: Dead production modules with zero callers (~1300 lines)
severity: medium
status: proposed
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

## Proposed fix

Either integrate these modules into production paths (per their RFCs) or gate them behind feature flags with `# Phase N: pending integration` markers and tracking breadcrumbs. Remove `render_decomposer_prompt` was already done.
