# Breadcrumbs

Defects, design questions, and improvements for software-factory-2. One file per item, numbered for reference. Numbers do not imply priority — see `severity` in each file's frontmatter.

Schema follows substrate's breadcrumbs convention; see `/projects/substrate/breadcrumbs/README.md` for the canonical reference.

## Schema

```yaml
---
number: "001"
title: Short descriptive title
severity: critical | high | medium | low
status: proposed | in_progress | implemented | obsolete
kind: bug | design | improvement
author: who-raised-it
date: "YYYY-MM-DD"
tags: [topic, stage-N, dep-substrate-NNN]
related: ["002", "003"]
---
```

## Severity

- **critical** — blocks correct operation; v2 cannot be trusted for stated guarantees
- **high** — load-bearing spec property unfulfilled; silent-correctness risk
- **medium** — defect with workaround or limited blast radius
- **low** — edge case, polish, or minor ergonomics

## Tags

Reusable tags:
- `stage-0` through `stage-10` — pipeline stage from spec §4
- `dep-substrate-NNN` — blocks on substrate breadcrumb NNN
- `channel-claude`, `channel-k2`, `channel-glm`, `channel-deepseek`, `channel-gemini`, `channel-opencode`
- `tier-a`, `tier-b`, `tier-c` — capability tier (spec §5)
- `runner`, `telemetry`, `gate`, `jury`, `race`, `failure-routing`

## Open

| # | Title | Severity | Status |
|---|---|---|---|
| 011 | Test gap — claim transition not asserted in worker loop tests | high | proposed |
| 012 | Context derivation tests should exercise both spec_file paths | high | proposed |
| 013 | Gate is syntactic-only — semantic gating is the central Phase 2 design question | high | proposed |

## Resolved

| # | Title | Severity | Resolution |
|---|---|---|---|
| 008 | Fixture AC-15 mislabel in 04-verify_event_errors.md | high | Fixed AC-15 text to describe verify_event rejection behavior |
| 009 | context_hash → artifact non-determinism; replay tests must assert structure | high | Added `structural_signature()` + `structurally_equivalent_pyi()` in gate.py with 10 tests |
| 010 | populate_work_items.py --reset does not clean workspace | high | Added `--workspace-root` argument; `shutil.rmtree` on `--reset` |
| 007 | Integration tests are stubs | medium | Replaced gate_process stub with real process_gate_item tests; Kimi fixed smoke test; added MockSubstrate pipeline tests |
| 006 | MockSubstrate needed for CI-portable tests | medium | Built MockSubstrate test double + 5 CI-portable pipeline tests |
| 005 | Spec content resolution for context derivation | high | Added spec_file config + loader; Phase 1 uses inline, Phase 2 needs section extraction |
| 004 | cannot_proceed routing has no workflow path | high | Added cannot_proceed terminal state + transition to both YAMLs; runner bypasses gate |
| 002 | Runner skeleton complexity risk | medium | Implemented: 7-module decomposition built per BC-002 spec |
| 003 | Runner idempotency on restart | high | Implemented: §9.12 spec amendment applied, workspace + tests done |
| 001 | Dead error codes: defined but never raised | low | Moved to substrate/breadcrumbs/026 — not a factory issue |
