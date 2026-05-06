# Software Factory v2 — Agent Guide

## Orientation

Read in this order:
1. `spec.md` — design spec, authoritative for every architectural decision.
2. `breadcrumbs/README.md` — open defects/design questions, sorted by severity.
3. `.factory/worklog.md` — most recent session entry, for current state.
4. `.factory/reflections/` — most recent reflection, for the prior agent's subjective read.

## What this project is

A pipeline that consumes a Level-1+ spec (produced by socratic-specification) and produces working, tested software for line-of-business tooling. Substrate (`/projects/substrate`) is the coordination/state spine.

The principal of this project is a **systems architect, not a developer**. Architectural decisions must respect that constraint: do not propose interventions that require code review, and do not assume the principal can debug subtle implementation bugs. Their value lands in spec quality, AC clarity, and outcome-level evaluation.

## Conventions

### Spec authority
- `spec.md` is authoritative. Implementation drift requires a spec amendment with rationale, not silent divergence.
- Spec amendments are made with a breadcrumb resolution note. Precedent: substrate BC-008.

### Breadcrumbs
- One file per defect/design-question/improvement under `breadcrumbs/`.
- Resolved items move to `breadcrumbs/resolved/` and the README index is updated.
- Same schema as substrate's `breadcrumbs/`. Reuse that README's frontmatter format.
- Use the `dep-substrate-*` tag for breadcrumbs that block on substrate work.

### Worklog and reflections
- `.factory/worklog.md` — reverse-chronological session log. Prepend new entries.
- `.factory/reflections/` — per-session subjective notes. One file per session, written via the `/reflect` skill.

### Session lifecycle
- `/reflect` — write a session reflection (system skill).
- `/end` — wrap up: update breadcrumbs, run reflect, commit (system skill).
- No factory-specific commands yet. Phase 1 will likely add `/factory-run`, `/factory-status`, `/factory-replay`.

## Status

**Phase 0 (current).** Design only. No runner code, no substrate workflow YAML, no channel adapters. The spec is the only artifact.

**Blocking on:** substrate Phase 2 stabilization. Specifically, BC-021 in substrate (hook consumer no reconnect) is a hard prerequisite for v2's hook-based stage triggering.

**Next concrete step:** wait for substrate stable, then begin Phase 1 (single-role end-to-end) per `spec.md` §9.

## What not to build yet

The phasing in `spec.md` §9 exists to prevent the v1 mistake of building the whole architecture at once. Do not implement:
- Channel adapters for any channel beyond Claude (CC) until Phase 3.
- Multi-channel jury gates until Phase 4.
- Race patterns until Phase 4.
- Any workflow beyond the single-role end-to-end loop until Phase 1 hits its >90% pass-rate target.

If you find yourself wanting to skip ahead, file a breadcrumb explaining why and let the principal decide.

## Pointers

- Substrate repo: `/projects/substrate`
- Socratic-specification repo (Stage 0 source): `/projects/socratic-specification`
- v1 software factory (reference for *what not to do*, not for code reuse): `/projects/software-factory`
