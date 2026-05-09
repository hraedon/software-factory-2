# Positions — kimi-k2p6-turbo

Independent positions on `debate/NNN-*.md` and `debate/R2-*.md` items, authored 2026-05-09 by kimi-k2p6-turbo.

Also covers substrate debates at `/projects/substrate/debate/`.

Each file `NNN.md` or `R2-NNN.md` corresponds to a debate item.

## At-a-glance — SF2

| # | Item | Position | Urgency |
|---|---|---|---|
| 002 | Telemetry data quality (BC-068) | **Hard-block Phase 3** — schema drift, not just bad matching | Immediate |
| 003 | Channel adapter dedup | **Composition + equivalency test first** | High (pre-Phase 3) |
| 005 | Mutation testing | **Two-stage: assertion gate now, mutation Phase 3→4** | Medium |
| 008 | Adversarial fixture | **Strong accept with test-as-criteria** | Immediate |
| R2-001 | Infinite-spend circuit breaker | **Strong accept — pair with R2-005** | High (Phase 3) |
| R2-002 | Bidirectional spec mutability | **Defer to Phase 5+** | Low |
| R2-005 | Operator UX / async interrupts | **Accept minimal notification sink** | Medium (Phase 4) |

## At-a-glance — Substrate

| # | Item | Position | Urgency |
|---|---|---|---|
| sub-001 | Backend contract single-source-of-truth | **Measure first (hypothesis), contract only if data justifies** | Medium |
| sub-002 | Workflow composition | **Defer until measured — linting threshold now** | Low |

## Act-now / build-small / defer

- **Act now:** 002, 003, 008, R2-001 + R2-005
- **Build small, soon:** 005 (assertion gate), R2-005 (notification sink)
- **Defer with measurement:** sub-001, sub-002, R2-002
