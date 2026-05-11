---
number: "078"
title: "Benchmark scope systematically excludes cross-module dependencies — Phase 2 exit criteria measured on easy case"
severity: high
status: implemented
kind: bug
author: deepseek-v4-pro (adversarial review — Session 20)
date: "2026-05-11"
tags: [stage-2, stage-3, stage-5, dep_resolution, gate, runner, telemetry]
related: ["076", "077", "074", "072"]
---

## Problem

The golden runs operate on two fixture classes with fundamentally different architectural complexity:

| Fixture class | Runs | Cross-module deps | Impl lock rate |
|---|---|---|---|
| Curated primary-spec (15 single-module items) | GR004, GR005 | None | 80–87% |
| cert-watch-mini (3 items with diamond deps) | GR006a, GR007, GR008, GR011 | `certificate_model` ← FR02, FR03 | 33–67% |
| cert-watch full (8 items, full DAG) | GR012 | 3 diamond consumers, library deps | 37.5% test_suite lock; implementations unreached |

Phase 2 self-assessment and exit criteria (e.g. `test_gr006a_meets_phase2_exit_threshold`) are measured against fixture classes that **systematically exclude cross-module dependencies** — the architectural pattern that exercises every pipeline component across seam boundaries. When cross-module deps are present, lock rates drop dramatically.

GR012 demonstrates the severity: with a realistic 8-spec DAG, the runner's query-order-dependent processing processes root dependencies last, causing 5/8 test_suites to fail because their dependency interface_specs weren't locked yet.

## Impact

The "80%+ implementation lock rate" framing overstates the pipeline's real-world readiness. The fixtures used to validate Phase 2 exit criteria do not exercise the architectural pattern known to cause failures. This creates a false confidence problem: operators reviewing telemetry see strong numbers on curated fixtures without realizing the structurally harder case is excluded.

## Proposed fix

1. Extend the cert-watch full fixture to a complete, self-contained DAG that exercises: independent foundation modules, single-dep modules, diamond dependencies, multi-hop chains, and non-FR library modules.
2. Define a Phase 2 exit criterion that requires >= 70% implementation lock rate on a fixture set that explicitly includes cross-module dependencies.
3. Add a criteria test (analogous to `test_gr006a_criteria.py`) for the full-DAG fixture that gates Phase 2 → Phase 3 promotion.
4. Resolve BC-077 (topological ordering) first, since it is a prerequisite for testing the full DAG end-to-end.

## Resolution

All four proposed fixes completed:

1. cert-watch full fixture extended with 8 work-units: diamond deps, library deps, multi-hop chains, non-FR modules.
2. GR-014 achieved 91% lock rate (20/22) on cert-watch full DAG — exceeds the 70% threshold.
3. Criteria tests added in `test_gr015_criteria.py` (7 skip-when-absent tests for full-DAG fixture).
4. BC-077 resolved (scheduler topological ordering) in Session 21; validated by GR-013 and GR-014.

Phase 2 exit criteria now measured against the hardest fixture class.
