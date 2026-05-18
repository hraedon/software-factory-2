---
number: "RFC-004"
title: "Auto-generated pipeline documentation — v1 docs froze while pipeline grew"
severity: medium
status: implemented
kind: improvement
author: adversarial-review
date: "2026-05-08"
tags: [docs, runner, dep-v1-docs]
related: ["042"]
---

## Problem

v1's README documented 7 pipeline stages. The actual pipeline ran 19 stages (BC-332 added InterfaceReview, PartialMerge, Wiring, Feedback, Cleanup, PhaseRecording, etc.). Documentation froze while the pipeline grew, creating a growing gap between what the docs said and what the system did.

v2 already has this pattern: AGENTS.md says "Phase 0 (current)" when Phase 2 is running (BC-042). The spec describes 10 stages but 3 are implemented. The `full_pipeline.yaml` declares 11 roles and 5 work-item types that have no implementation.

## Proposal

Generate pipeline documentation from the authoritative sources:
1. Workflow YAML → pipeline stage diagram (states, transitions, allowed roles).
2. Work-item type definitions → artifact contract table (required fields, refs).
3. `prompts/*.md` → role responsibilities summary (extract first paragraphs + rules lists).
4. `router.py:_PHASE2_DISPATCH` → failure routing table.

A `make docs` target regenerates these from source on every change. This ensures documentation is always a deterministic view of the current system state, never hand-maintained.

## Dependencies

Low priority now (3 stages, 3 roles). Becomes important at Phase 3 when the fleet grows beyond what a human can mentally track.
