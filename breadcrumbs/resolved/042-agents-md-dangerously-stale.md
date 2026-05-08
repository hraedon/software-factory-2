---
number: "042"
title: "AGENTS.md dangerously stale — claims Phase 0 design-only, repo is deep in Phase 2"
severity: high
status: resolved
kind: bug
author: adversarial-review
date: "2026-05-08"
tags: [docs, runner]
related: []
---

## Problem

`AGENTS.md` §Status says:

> **Phase 0 (current).** Design only. No runner code, no substrate workflow YAML, no channel adapters. The spec is the only artifact.

The repo is deep in Phase 2 with:
- 259 passing tests
- Full runner, scheduler, gate, 2 channel adapters
- 3 golden runs executed
- 2 workflow YAMLs (phase1, phase2) plus full_pipeline.yaml

An agent following AGENTS.md's "Read in this order" directive will be severely misled about what exists and what needs building. Any agent that believes the doc will waste time trying to build things that are already built, or skip testing infrastructure that exists.

## Fix

1. Update Status section to reflect current phase (~Phase 2, single-channel pipeline validation).
2. Update "What not to build yet" to reflect current actual constraints (no multi-channel, no jury/race, no non-Claude channels except OpenCode stub).
3. Keep the phasing discipline language — it's still correct. Just the phase label and inventory are wrong.
