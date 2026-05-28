---
number: "173"
title: "Workflow composition migration complete — extends: adopted for phase2-5"
severity: low
status: implemented
kind: improvement
author: opencode
date: "2026-05-16"
tags: [workflows, regista, rfc]
related: ["RFC-028"]
---

## Problem

Phase 1-5 workflow YAMLs had ~58% structural duplication. Each phase file repeated states, transitions, roles, work_item_types, and link_types verbatim, making new phase additions error-prone.

## Resolution

Migrated phase2-5 YAMLs to use Regista's `extends:` composition feature:

- `phase2.yaml` extends `./phase1.yaml`, adding test_author/implementer roles, test_suite/implementation work_item_types, 3 link types, and `allowed_roles__append` on 5 transitions.
- `phase3.yaml` extends `./phase2.yaml` — just version bump (4 lines, down from 192).
- `phase4.yaml` extends `./phase3.yaml`, adding cross_family_reviewer/frontier_judge roles, review/jury work item types, 2 link types.
- `phase5.yaml` extends `./phase4.yaml`, adding integrator/outcome_verifier roles, integration/outcome_verification work item types, 3 link types.
- `full_pipeline.yaml` remains standalone (too divergent per MIGRATION_PLAN.md).

Total: 1133 → 421 lines (62.8% reduction).

Also updated:
- `src/factory/pipeline_docs.py`: `_load_workflow_yaml()` uses `resolve_includes()` instead of `yaml.safe_load()`.
- Regista `InMemorySubstrate.register_workflow_file()` and `Regista.register_workflow_file()`: resolve `extends:` before registration.
- 5 test call sites changed from `register_workflow(raw_yaml)` to `register_workflow_file(path)`.

## Known limitation

Regista's keyed-list merge places child items before parent items. This changes list ordering (roles, work_item_types, link_types, transitions) from the monolithic order but is functionally equivalent. Content hashes differ; semantic identity verified via `scripts/migrate_workflows.py --verify`.