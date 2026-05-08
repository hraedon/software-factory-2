---
number: "RFC-001"
title: "Prompt conflict detection — v1 BC-383 shows silent failure when role prompts contradict"
severity: high
status: proposed
kind: design
author: adversarial-review
date: "2026-05-08"
tags: [prompts, stage-2, stage-3, stage-4, dep-v1-383]
related: ["050"]
---

## Problem

v1's BC-383: implementer prompt rules conflicted. The ownership prompt said "shared-frozen files are DO NOT EDIT" but the review prompt said "MUST edit `deps_base.py`." Agents facing contradictory instructions silently defaulted to inaction. Tests passed via mocks, no errors surfaced, and the pipeline delivered non-functional software.

v2 already has one prompt contradiction (BC-050): `interface_architect.md`'s worked example uses `from typing import Union` while `implementer.md` forbids it — and the lint gate rejects it. This is the same class of bug at a smaller scale.

As v2 adds more roles (Phase 3: cross-family reviewer, Phase 4: frontier judge, coherence reviewer), the prompt surface grows. Each new prompt is a potential contradiction with every existing prompt. Manual review doesn't scale — the system that *should* catch this is also the system producing the contradictions.

## Proposal

Build a mechanical prompt audit tool that checks for:
1. **Contradictory directives**: e.g., "Do X" in prompt A vs. "Never do X" in prompt B targeting the same artifact.
2. **Orphaned references**: prompt A instructs consuming an artifact that prompt B's contract doesn't declare it will produce.
3. **Style drift**: prompt A's worked example uses patterns prompt B forbids (BC-050).

This can start simple — a pytest suite that reads all `prompts/*.md` files and checks for known-incompatible patterns — and grow into AST-based semantic analysis over time.

## Dependencies

Awaits Phase 3+ when multiple role prompts exist. Low urgency now (only 3 prompts) but should be scoped before prompt count exceeds ~6.
