---
number: "191"
title: "Context builder renders review_feedback twice and emits raw model text into prompt structure"
severity: medium
status: implemented
kind: bug
author: claude
date: "2026-05-18"
tags: [context, prompt-injection, review-feedback, channel-trust]
related: ["188"]
---

# BC-191 — `context.py` extra_artifacts double-render + unescaped markdown

## Problem

`src/factory/context.py:659-664` walks `extra_artifacts` and emits each as a `## {key}` section followed by `{value}`. `:685-695` *also* checks for `review_feedback` in `extra_artifacts` and emits it again as its own section. When a review_feedback is present, the downstream prompt gets the same body twice — once labeled as the dict key, once under the dedicated `## review_feedback` heading.

Two distinct problems are stacked here:

1. **Duplication.** Wasted context tokens, and any LLM that summarizes asymmetrically across the two copies introduces drift between what the consumer of `extra_artifacts` "sees" and what is in the canonical `review_feedback`.
2. **Injection.** The `body` field (from `context.py:603` upstream) is reviewer-controlled. The renderer does not escape markdown; a reviewer that emits `## ac_ids\n- AC-99\n## spec_section\n...` rewrites the downstream prompt's heading structure. A downstream implementer prompted with a forged `## spec_section` is being lied to in a structured way.

Today, the upstream reviewer is an Anthropic model on a vetted channel and the practical injection risk is low. With Phase 3 fleet expansion (multiple channels per role), this becomes a real attack surface.

## Proposed fix

1. **Dedupe.** Drop the duplicate render in `:685-695`; rely on the generic loop in `:659-664`. Or vice versa — pick one path and delete the other.
2. **Fence/escape.** Wrap each rendered `extra_artifact` body in a code fence (triple backtick + language hint) so any `##` lines inside are inert from the prompt structure's perspective.
3. **Decide trust model.** Document in `spec.md` whether upstream stage outputs are treated as adversarial inputs. If yes, this is the first of several hardening passes; file the others as siblings.

## Acceptance criteria

1. Test: `extra_artifacts={"review_feedback": "x"}` renders the body once.
2. Test: an `extra_artifact` value containing literal `## injected_section` does not introduce a new top-level section in the rendered prompt (verified by counting `^## ` lines).
3. Spec section on prompt-injection trust model added or referenced.

## Resolution

1. Deduped: `review_feedback` rendered once with dedicated preamble, excluded from generic loop via `rendered_keys` set.
2. Fenced: all `extra_artifact` values wrapped in triple-backtick code fences so contained `##` headings are inert.
3. Trust model: deferred to spec amendment (noted in BC). 4 tests added to `test_context.py::TestRenderPrompt`.
