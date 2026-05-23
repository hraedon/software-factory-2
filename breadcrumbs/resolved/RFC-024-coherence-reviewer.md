---
number: "RFC-024"
title: "Coherence reviewer — declared role with zero design or implementation"
severity: high
status: resolved
kind: design
author: agent
date: "2026-05-15"
tags: [rfc, stage-8, coherence-reviewer, role-design]
related: []
---

## Summary

The `coherence_reviewer` role was declared in:
- ~~spec.md §4 line 103: listed in the substrate workflow roles alongside interface_architect, implementer, integrator, etc.~~ **Removed 2026-05-22.**
- ~~spec.md §5 line 135: bound to Gemini CLI, described as "probationary; uses long-context advantage for cross-module consistency checking."~~ **Removed 2026-05-22.**
- ~~constants.py line 28: `ROLE_COHERENCE_REVIEWER = "coherence_reviewer"`~~ **Removed 2026-05-22.**
- ~~workflows/full_pipeline.yaml: listed in actor_roles.~~ **Removed 2026-05-22.**

It had zero design elaboration, zero prompts, zero routing, zero tests, and zero implementation.

## Resolution

**Option A (delete) chosen on 2026-05-22.**

The `coherence_reviewer` role was removed from all four locations because it was dead configuration: the only code reference was a constant string, and there were zero prompts, zero routing rules, zero tests, and zero substrate work-item type for it to consume. The `full_pipeline.yaml` referenced it in `actor_roles`, which would have caused the runner to look for a channel binding that did not exist.

If real workloads in Phase 6 demonstrate a structural-coherence gap that integrator + outcome_verifier miss, a new RFC should be filed with:
1. Concrete evidence from at least one workload showing the gap.
2. A defined work-item type, prompt template, and output schema.
3. Routing rules for pass, fail, and cannot_proceed.
4. A placement in the pipeline (likely post-integration, pre-outcome-verification).

Until then, the role is not reinstantiated. Premature roles are CLASS-012 fuel.
