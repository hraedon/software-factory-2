---
number: "RFC-014"
title: "Staff engineer summarizer — compress outer-path failure history into actionable constraints"
severity: medium
status: proposed
kind: design
author: gemini-adversarial-review + opus-refinement
date: "2026-05-11"
tags: [runner, context, inner-gate, outer-retry, rfc, phase4]
related: ["RFC-013"]
---

## Problem

RFC-013 feeds raw, truncated tool output (pytest tracebacks, mypy errors) into the inner gate retry prompt. This works well for the inner loop — models read pytest output fine, and 2KB of traceback is directly actionable.

But the outer retry path has a different problem. When the inner gate exhausts retries and the work item is rerouted (reclaimed by the runner on a subsequent attempt), the model receives `prior_failures` derived from `FailureEntry.diagnostic` — semicolon-joined strings of truncated diagnostic lines from potentially multiple attempts. By attempt 3-4, the model is reading its own natural-language failure summaries, not raw tool output. This is where LLMs hallucinate: they start "fixing" errors from attempt 1 that were already resolved in attempt 2.

## Proposed enhancement

For the outer retry path (when the inner gate exhausts and the work item is re-claimed), compress failure history through a "staff engineer summarizer" — a cheap, fast model (K2, Haiku, or similar) that reads all prior failure entries and outputs a strict 3-5 bullet-point constraint list.

Example output:

```
1. You keep trying to import os; use pathlib instead.
2. The mock for Database is missing the commit() method.
3. Do not change the return type from Certificate to dict.
4. The AC-03 validation requires handling None input — add an explicit check.
```

The implementer then receives a fresh prompt with exactly those constraints, rather than accumulated diagnostic history.

## Inner vs outer path distinction

| Path | Current behavior | Proposed behavior |
|---|---|---|
| Inner loop (within `_inner_gate_loop`) | RFC-013: raw truncated tool output | Keep raw output — models read tracebacks fine |
| Outer retry (work item re-claimed after exhaustion) | `prior_failures` with semicolon-joined diagnostics | Summarized constraint list from staff engineer |

The key insight (from Opus): models hallucinate when reading their own prior natural-language reasoning, not when reading pytest output. Raw tracebacks in the inner loop are fine; the summarizer is only needed for the outer path where accumulated failure history becomes noise.

## Implementation sketch

1. In `derive_context()` (or `derive_implementer_context()`), when `prior_failures` is non-empty and this is an outer retry (not inner gate), invoke a summarization call:

```python
if len(prior_failures) >= 2:
    summary = _summarize_failures(prior_failures, cheap_model)
    # Replace prior_failures with summarized constraints
```

2. `_summarize_failures()` sends the failure history to a cheap model with a strict prompt: "Given these N failed attempts, output exactly 3-5 bullet-point constraints for the next attempt. Do not speculate. Only list patterns you can verify from the evidence."

3. The constraint list replaces `prior_failures` in the `PromptContext`, so `render_prompt` emits clean constraints instead of accumulated diagnostics.

4. The `context_hash` changes (different prompt content), so the model generates fresh output rather than attempting to match a prior hash.

## Cost

One additional model call per outer retry, using the cheapest available model (~$0.001-0.01 depending on provider). This is negligible compared to the cost of the implementer call itself.

## Phase placement

Phase 4. The summarizer is most valuable when the factory has jury gates and multi-model dispatch — the outer retry path becomes common. In Phase 3, most items lock within 1-2 attempts (GR-014: 91% first-pass), so the outer retry path is rarely exercised.

## What this doesn't replace

- RFC-013 (inner gate feedback) — raw tool output is still the right approach for the inner loop
- The existing `prior_failures` mechanism — it's still used for context hashing and telemetry; the summarizer only replaces what the model sees
