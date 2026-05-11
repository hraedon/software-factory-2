---
number: "RFC-010"
title: "Fixture taxonomy — classify fixtures by architectural complexity class and gate Phase N exit criteria on the hardest exercised class"
severity: high
status: deferred
kind: design
author: deepseek-v4-pro (adversarial review — Session 20)
date: "2026-05-11"
tags: [stage-2, stage-3, stage-5, test, telemetry]
related: ["078", "081", "RC-003"]
phase_needed: "Phase 2 exit criteria (immediate)"
---

## Problem

Currently, golden runs use different fixture classes (single-module curated, cross-module mini, cross-module full DAG) with no systematic method for determining which class is sufficient to validate which pipeline stage. Phase 2 exit criteria are measured against the single-module curated set (80-87% impl lock rate) while cross-module fixtures (the structurally harder case) show 33-67% lock rates on the same channels.

This creates a false confidence problem: exit criteria are met on the easy case, but the hard case — the one that exercises every seam in the pipeline — is a known failure mode with no criteria gate.

## Proposed design

Introduce a fixture taxonomy that classifies test fixtures by the architectural patterns they exercise:

| Class | Description | Patterns exercised |
|---|---|---|
| **A: Single-module** | One interface_spec, no deps | Basic role prompts, single artifact lifecycle |
| **B: Linear chain** | N specs in dependency chain (A → B → C) | Sequential dep resolution, context injection |
| **C: Diamond deps** | One root, N consumers (minimum 3 consumers) | Dep resolution, stub-vs-impl, concurrent resolution |
| **D: Full DAG** | 5+ specs with mixed shapes, non-FR modules, library deps | Topological ordering, multi-hop chains, all of above |

Each phase's exit criteria require a specific minimum fixture class:

| Phase | Minimum fixture class | Binding criterion |
|---|---|---|
| Phase 1 | Class A | >= 90% first-attempt spec lock rate |
| Phase 2 | Class C | >= 70% impl lock rate on diamond fixtures |
| Phase 3 | Class C | >= 70% impl lock rate on diamond fixtures with 2+ channels |
| Phase 4 | Class D | >= 70% impl lock rate on full DAG with jury gates |
| Phase 5 | Class D | >= 80% overall lock rate on real workload |

Fixture classification is declarative (a `class` field in the fixture directory's metadata) and validated by a simple script that checks the dependency graph structure matches the claimed class.

## Why deferred

This is a design proposal that requires the principal's buy-in — it changes how exit criteria are defined and measured. It is not a code defect; it's a process/architecture change. File now because BC-078 (benchmark scope) and BC-081 (missing criteria test) are concrete manifestations of the gap, and the principal should decide whether to adopt the taxonomy or address the gap through other means.
