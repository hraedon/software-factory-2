# Software Factory v2 — Agent Guide

## Orientation

Read in this order:
1. `spec.md` — design spec, authoritative for every architectural decision.
2. `breadcrumbs/README.md` — open defects/design questions/RFCs, sorted by severity.
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
- Active bugs and improvements use numeric prefixes (`054`, `055`).
- Design proposals awaiting future phases use `RFC-` prefixes (`RFC-001`, `RFC-002`). RFCs are NOT actionable yet — they are recorded design decisions for later stages.
- Resolved items move to `breadcrumbs/resolved/` and the README index is updated.
- Same schema as substrate's `breadcrumbs/`. Reuse that README's frontmatter format.
- Use the `dep-substrate-*` tag for breadcrumbs that block on substrate work.
- Use the `dep-v1-NNN` tag for breadcrumbs that block on lessons from v1 factory.

### Default values
- All defaults live in `FactoryConfig` or are derived from it. No inline defaults, no hardcoded identifiers, no bare strings in function bodies that could appear in another file. Precedent: v1's "string constant gravity" where `"claude"` accreted into 7 copies across 5 files.

### Worklog and reflections
- `.factory/worklog.md` — reverse-chronological session log. Prepend new entries.
- `.factory/reflections/` — per-session subjective notes. One file per session, written via the `/reflect` skill.

### Session lifecycle
- `/reflect` — write a session reflection (system skill).
- `/end` — wrap up: update breadcrumbs, run reflect, commit (system skill).

## Status

**Phase 2 (current).** Sequential single-channel pipeline validation. Phase 1 (single-role end-to-end) exit criteria met (>90% pass rate on interface_spec). Phase 2 adds test_author and implementer roles with scheduler-driven handoffs.

**What exists:**
- 7-module runner: runner, gate, gate_process, router, scheduler, config, workspace
- 2 channel adapters: ClaudeCodeChannel (stable), OpenCodeChannel (stub, BC-040)
- 2 workflow YAMLs: phase1.yaml (single-role), phase2.yaml (3-stage pipeline)
- 260 passing tests, 0 lint errors
- 3 golden runs executed against curated spec fixtures
  - 001: 12/15 interface_specs locked (Phase 1)
  - 002: 15/15 interface_specs + 15/15 test_suites, 0/15 implementations (module resolution bug, fixed)
  - 003: 15/15 interface_specs + 12/15 test_suites, 2/12 implementations locked, 10 escalated (lint prompt quality issue, BC-039/040 applied since)

**Known issues:** 5 open breadcrumbs (0 critical, 0 high, 4 medium, 1 low) + 5 RFCs. BC-056, BC-045 resolved this session. See `breadcrumbs/README.md`.

**Blocking on:** nothing. Substrate is stable enough for sequential single-channel mode. The spec's BC-021 reference is historical — hooks work sufficiently for the current pipeline shape.

**Next concrete step:** resolve remaining high breadcrumbs (BC-055 stage contracts blocking — already implemented, needs closed) then execute Golden Run 004 to validate prompt fixes and family-per-invocation telemetry.

## What not to build yet

The phasing in `spec.md` §10 exists to prevent the v1 mistake of building the whole architecture at once. Current constraints:
- Single channel only (`claude-code` or single `opencode`). Multi-channel dispatch raises `NotImplementedError`.
- Three-role pipeline only (interface_architect, test_author, implementer). Roles beyond these have no implementation.
- Mechanical gates only. Cross-family review, frontier jury, and coherence review are Phase 3-4.
- No jury gates or race patterns until Phase 4.
- Channel adapters for K2, GLM, DeepSeek, Gemini deferred until Phase 3.

If you find yourself wanting to skip ahead, file a breadcrumb explaining why and let the principal decide.

## Pointers

- Substrate repo: `/projects/substrate`
- Socratic-specification repo (Stage 0 source): `/projects/socratic-specification`
- v1 software factory (reference for *what not to do*, not for code reuse): `/projects/software-factory`

## Testing

```bash
make test    # 259 tests, ~16s
make lint    # ruff check + format (no errors)
make check   # lint + test (full CI gate)
```
