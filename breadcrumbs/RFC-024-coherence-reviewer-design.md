---
number: "RFC-024"
title: "Coherence reviewer — declared role with zero design or implementation"
severity: high
status: proposed
kind: design
author: agent
date: "2026-05-15"
tags: [rfc, stage-8, coherence-reviewer, role-design]
related: []
---

## Summary

The `coherence_reviewer` role is declared in:
- **spec.md §4** line 103: listed in the substrate workflow roles alongside interface_architect, implementer, integrator, etc.
- **spec.md §5** line 135: bound to Gemini CLI, described as "probationary; uses long-context advantage for cross-module consistency checking."
- **constants.py** line 28: `ROLE_COHERENCE_REVIEWER = "coherence_reviewer"` — the only code reference.
- **workflows/full_pipeline.yaml**: listed in actor_roles.

It has zero design elaboration, zero prompts, zero routing, zero tests, and zero implementation. The role name hints at cross-module consistency checking (the spec calls it a "long-context advantage"), but there's no specification of:

1. **Trigger** — Does it run per-integration (after each integration work item locks)? Per-DAG (after all integrations are done)? Per-phase (after outcome verification)?
2. **Inputs** — Does it consume the full assembled_tree (like the integrator produces)? Does it need all review/jury verdicts? Does it need the original spec?
3. **Output** — Does it produce a pass/fail verdict? Structured findings? A coherence score? A routing_hint?
4. **Failure routing** — If coherence review fails, does it route to integrator (re-assemble with fixes), outcome_verifier (re-verify), or interface_architect (contract revision)?
5. **Relationship to existing roles** — How does it differ from cross_family_reviewer (reviews a single work unit) and outcome_verifier (runs assembled software end-to-end)? The coherence reviewer sits between integration and outcome verification — is it a "look at the whole thing for structural problems before running it"?

## Why it matters

Dead configuration is dangerous in a pipeline where configuration drives behavior. The `full_pipeline.yaml` declares `coherence_reviewer` as an actor role, which means any substrate project using that workflow will register it. If a future Phase tries to run `full_pipeline.yaml` for a golden run, the runner will try to find a channel binding for `coherence_reviewer` and fail at runtime (or silently skip it via `_role_for_type` returning `None` if no work items of that type exist). Either way, it's configuration that cannot be exercised.

More importantly, the role fills a real gap in the pipeline: integration ensures the modules compile together, outcome verification ensures the assembled software runs against ACs, but neither checks for *structural coherence* — are there duplicate responsibilities across modules? Is there a circular dependency that will cause runtime issues? Does the module boundary make sense? This is a genuinely useful role, but its trigger, inputs, and routing need design.

## Design questions

1. **Where in the pipeline?** The most natural placement is after integration locks, before outcome verification. This gives the reviewer the assembled tree and the integration test results. If it passes, outcome verification runs the assembled software. If it fails, the integrator gets structured feedback.
2. **What does it check?** Candidate dimensions:
   - Module boundary violations (module A reaches into module B's internals)
   - API consistency across modules (same concept named differently in two modules)
   - Missing or redundant modules (a concern that no module owns, or two modules that overlap)
   - Circular dependency detection beyond what import resolution catches
3. **Output schema?** A verdict JSON similar to outcome_verifier: `{ "verdict": "pass"|"fail"|"cannot_proceed", "findings": [...], "routing_hint": { "work_item_type": "...", "reason": "..." } }`.
4. **Routing on failure?** Most findings would route to the integrator (re-assemble with fixes). Some could route to interface_architect (the module decomposition was wrong). The `routing_hint` mechanism from Stage 9 would be reused.

## Phase needed

Phase 6 or later. Phase 5 is synthetic-fixture validation. The coherence_reviewer requires a multi-module workload with genuine cross-module issues, which doesn't exist in the current fixtures.
