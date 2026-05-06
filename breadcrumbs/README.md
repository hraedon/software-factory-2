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
| (none) | | | |

## Resolved

| # | Title | Severity | Resolution |
|---|---|---|---|
| 002 | Runner skeleton complexity risk | medium | Implemented: 7-module decomposition built per BC-002 spec |
| 003 | Runner idempotency on restart | high | Implemented: §9.12 spec amendment applied, workspace + tests done |
| 001 | Dead error codes: defined but never raised | low | Moved to substrate/breadcrumbs/026 — not a factory issue |
