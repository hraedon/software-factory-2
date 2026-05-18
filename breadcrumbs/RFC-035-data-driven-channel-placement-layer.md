---
number: "RFC-035"
title: "Data-driven channel placement layer: consume PassRateRow to propose role→channel config"
severity: high
status: proposed
kind: design
author: claude
date: "2026-05-18"
tags: [placement, fleet-integration, phase-3-blocker]
related: ["RFC-034"]
---

# RFC-035 — Placement layer

## Motivation

`PipelineRuntime.channel_for_role` (`src/factory/runtime.py:27-45`) is a flat dict lookup from `FactoryConfig.roles`. `_create_channels` (`src/factory/runner.py:1131-1148`) instantiates whatever the YAML names. Nothing in `src/` consumes `compute_pass_rates` or `PassRateRow` to produce a placement *decision*. "Fleet integration" in spec §10 today means a human edits YAML between runs based on visually reading the pass-rate table.

This is fine at 2 channels and 5 roles. At Phase 3's intended scale (≥4 channels × ≥7 roles × multiple gates), it is a combinatorial editor's job.

## Proposal

Introduce `factory.placement` with three pieces:

1. **`Placement.propose(history: PassRateTable, config: FactoryConfig, policy: PlacementPolicy) -> FactoryConfig.Diff`** — returns a structured diff (role X currently → channel Y, propose channel Z, rationale and effect-size estimate) rather than mutating config directly.
2. **`PlacementPolicy`** — declares the decision rule: e.g., "highest pass rate with ≥ N samples and ≥ K confidence; fall back to current"; "lowest cost meeting threshold T"; "prefer Anthropic for review roles unless dominated". Policy is data, not code, so the principal can A/B placement strategies without touching the runner.
3. **`Placement.apply(diff, mode={dry-run|propose-pr|live})`** — three modes. Default `dry-run` writes the diff to a file under `runs/`. `propose-pr` opens a PR against the config. `live` rewrites the YAML in place (gated behind explicit consent).

Crucially, **the runner does not auto-apply**. Placement is a separate cron / CLI invocation. The principal stays in the decision loop until enough runs validate the policy.

## Why this is a Phase-3 blocker, not a Phase-4 nice-to-have

Without (1), there is no operational answer to "did adding channel Z improve the fleet?" — the question requires a decision rule, which is exactly what the placement layer encodes. Without an answer to that, Phase 3's central thesis (more channels = better fleet) is unfalsifiable.

## Open questions

1. Does this depend on RFC-034 (model identity in telemetry)? **Yes** — without resolved model strings, "channel Y is best" is conflated with "model snapshot Y was on the day this data was collected."
2. Should `Placement.propose` consume `runs/` artifacts directly or read from substrate? **Substrate.** Single source of truth; `runs/` is for human inspection.
3. How does this interact with the principal-review-surface (RFC-026)? Placement diffs should be a first-class object in that surface.

## Acceptance criteria

1. `placement.propose` invoked on the GR-038 dataset produces a non-empty diff with rationale for each proposed change.
2. `dry-run` mode produces a diff file; no config mutation.
3. Test: a synthetic dataset where channel A dominates channel B at role R produces a diff moving R from B to A.
