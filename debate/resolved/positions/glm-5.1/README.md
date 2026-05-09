# Positions — glm-5.1

Independent positions on `debate/NNN-*.md` items, authored 2026-05-09 by glm-5.1. Kept in this subfolder to avoid contaminating the original debate items before parallel review.

Each file `NNN.md` corresponds to `debate/NNN-*.md`.

## Round 1

| # | Item | Position | Urgency |
|---|---|---|---|
| 001 | Behavioral / Playwright gate | Defer to Phase 5; spec amendment + stub only | Low (now), High (Phase 5) |
| 002 | Telemetry data quality (BC-068) | **Hard-block Phase 3** | Immediate |
| 003 | Channel adapter dedup | Accept principle; prefer composition over inheritance | High (pre-Phase 3) |
| 004 | Pipeline checkpoints | Defer; substrate state is already the checkpoint | Low |
| 005 | Mutation testing | Accept timing; assertion-counting gate first, mutation in Phase 4 | Medium (Phase 3→4) |
| 006 | Per-project venv | Accept, narrow to 50-line helper; defer to pre-Phase 5 | Medium (pre-Phase 5) |
| 007 | Credential management | Accept schema; reject rotation/audit for Phase 3 | Medium (pre-Phase 3) |
| 008 | Adversarial fixture | Accept; 3-of-5 characteristics before Phase 2 close | Immediate |
| 009 | Event schema evolution | Accept consumer-level pilot; defer substrate registry | Medium |
| 010 | Event log retention | Defer; instrument with metrics, auto-breadcrumb at thresholds | Low |

## Round 2 (Gemini R2 items)

| # | Item | Position | Urgency |
|---|---|---|---|
| R2-001 | Infinite spend circuit breaker | Accept reframed as wall-clock budget, not financial | High (pre-Phase 3) |
| R2-002 | Bidirectional spec mutability | Defer formal mechanism; add `spec_impossibility` fast-path now | Low (now), High (Phase 5) |
| R2-003 | Database migration strategy | Accept as mechanical gate; Alembic gate pre-Phase 5 | Medium (pre-Phase 5) |
| R2-004 | Security / supply-chain gates | Accept `bandit` now, `pip-audit` pre-Phase 5; reject trufflehog/semgrep | Medium (pre-Phase 5) |
| R2-005 | Operator UX / async interrupts | Accept webhook-only, factory-side; reject substrate-side / dashboard | Medium (pre-Phase 3) |
| R2-006 | Dead code / refactoring lifecycle | Accept as trivial runbook extension; reject consolidation agent | Low |

## New items raised by glm-5.1

| # | Item | Position | Urgency |
|---|---|---|---|
| 011 | Prompt versioning in telemetry | **Accept; build alongside BC-068** | High (pre-Phase 3) |
| 012 | Attempt-level latency tracking | Accept; spec requires it, implementation lacks it | Medium (pre-Phase 3) |

## Act-now / build-small / defer

- **Act now:** 002, 003, 008, 011 (pair with BC-068)
- **Build small, soon:** 005 (assertion gate), 006, 007 (schema only), R2-001 (wall-clock budget), R2-005 (webhook), 012 (latency)
- **Defer with stub:** 001, 004, 009-pilot, 010-instrument, R2-002 (fast-path only now)
- **Defer to Phase 5+:** R2-003, R2-004 (pip-audit)
