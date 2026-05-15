---
number: "RFC-023"
title: "Decomposer role — Stage 1 pipeline cannot consume arbitrary specs"
severity: high
status: proposed
kind: design
author: agent
date: "2026-05-15"
tags: [rfc, stage-1, pipeline, decomposition]
related: []
---

## Summary

The decomposer (Stage 1) is declared in spec §4 (lines 46-49) as "reads spec.yaml; produces work-item DAG" and is listed in the binding table (§5 line 126, Claude CC headless default). It has zero implementation: no prompt template, no runner handler, no router entry, no scheduler topology.

The current pipeline completely sidesteps this role — `populate_work_items.py` reads pre-authored fixture YAMLs and creates work items from hand-crafted metadata. Every golden run to date (GR-001 through GR-029) has operated on human-designed DAGs, not on model-derived decomposition.

This is the single largest architectural gap in the codebase. Every other stage (interface_architect through outcome_verifier) has at minimum a skeleton. Stage 1 has nothing.

## Why it matters

The factory's value proposition is "consumes a specification and produces working software." Without decomposition, the pipeline can only process fixtures that a human has already decomposed into the "right" work-unit granularity. This means:

1. **All measured lock rates are on human-optimized DAGs.** The 88-100% lock rates on cert-watch are not representative — cert-watch was decomposed by the principal into 8 natural modules (certificate_model, FR-01–FR-05, cert_chain_library, database_layer). A model-driven decomposition of a raw spec will produce different granularity, different dependency graphs, and different failure modes.

2. **The pipeline cannot accept unstructured specs.** The spec-to-work-item boundary is a human step. This violates the spec's own Stage 0→1 handoff (Socratic elaboration produces spec.yaml; Stage 1 produces the DAG automatically).

3. **No design exists for model-driven decomposition.** The design questions are unanswered:
   - How does the decomposer decide granularity? What heuristic prevents over-splitting (too many fine-grained items) or under-splitting (one monolithic implementation)?
   - How does it handle cross-cutting concerns (logging, error handling, config) that don't map to a single work unit?
   - What does "decomposition produce a DAG" mean in practice — does it create substrate work items directly, or produce a YAML manifest that `populate_work_items.py` consumes?
   - How does the decomposer interact with the spec linting system (BC-127) and AC extraction (BC-130)?
   - What is the retry/failure path when the decomposer produces a bad decomposition?

## Design sketch (not a decision)

The simplest viable decomposer would:
1. Read spec.yaml (output of Stage 0, socratic-specification).
2. For each FR/requirement block, create an interface_spec work item with:
   - `spec_section` = the FR identifier
   - `ac_ids` = extracted from the block
   - `dependency_refs` = declared or inferred cross-module refs
   - `module_name` = derived from the block title
3. Write a `decomposition.yaml` manifest to the workspace as an audit trail.
4. Let the existing scheduler handle downstream creation (test_suite → implementation → review → ...).

The hard part is dependency inference (which FR depends on which) and granularity decisions (when does a requirement become 3 work units instead of 1). A reasonable starting point is "one interface_spec per FR/requirement block in the spec," which is what the human-authored cert-watch fixture already does.

## Not in scope

- The Stage 0 (socratic-specification) integration — that's a separate concern about consuming spec.md → spec.yaml.
- Multi-work-unit decomposition of a single FR — the Phase 5 scope is "one work unit per FR."
- The decomposer prompt — needs empirical iteration once the skeleton exists and produces real decompositions.

## Phase needed

Phase 6 (generalization). Phase 5 is synthetic-fixture validation with hand-crafted DAGs. The decomposer is the bridge to real workloads.
