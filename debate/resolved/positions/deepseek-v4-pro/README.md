# Positions — deepseek-v4-pro

Independent positions on `debate/NNN-*.md` items, authored 2026-05-09 by deepseek-v4-pro. Kept in this subfolder to avoid contaminating the original debate items before parallel review.

Also covers regista debates at `/projects/regista/debate/`.

Each file `NNN.md` corresponds to `debate/NNN-*.md`.

## At-a-glance — SF2

| # | Item | Position | Urgency |
|---|---|---|---|
| 001 | Behavioral / Playwright gate | Reject stub-only; build a concrete test that fails, then fix | Low-now, High-Phase-5 |
| 002 | Telemetry data quality (BC-068) | Fix now; colleague already on BC-068, verify with replay test | Immediate |
| 003 | Channel adapter dedup (`SubprocessChannel`) | Accept; refactor + test before any 3rd adapter | High (pre-Phase 3) |
| 004 | Pipeline checkpoints | Defer; not enough data to build | Low |
| 005 | Mutation testing | Accept; build and test before Phase 4 jury | Medium |
| 006 | Per-project venv | Accept narrow; test before Phase 5 | Medium |
| 007 | Credential management | Accept schema and test; reject rotation machinery | Medium (pre-Phase 3) |
| 008 | Adversarial fixture (cert-watch GR006a) | Accept; run with concrete pass/fail tests | Immediate |
| 009 | Event schema evolution | Accept consumer-level pilot and test | Medium |
| 010 | Event log retention | Defer; insufficient data | Low |

## R2 items (gemini's new round)

| # | Item | Where I add value | Urgency |
|---|---|---|---|
| R2-001 | Infinite-spend circuit breaker | Accept with test; agree with claude | High (pre-Phase 3) |
| R2-002 | Bidirectional spec mutability | Omitted — agree with claude's deferral | — |
| R2-003 | Database migration strategy | Accept; round-trip test IS the gate | Medium (pre-Phase 5) |
| R2-004 | Security & supply-chain gates | Accept; false-positive allowlist is load-bearing | Medium (pre-Phase 5) |
| R2-005 | Operator UX & async interrupts | Accept minimal; ADD approval response path to notification | Medium (Phase 4) |
| R2-006 | Dead code lifecycle | Omitted — agree with claude's audit extension | — |

## New items I raised

| # | Item | Position | Urgency |
|---|---|---|---|
| NEW-001 | Prompt version in ActorMetadata | Build before Phase 3; telemetry is cross-run incomparable without it | High (pre-Phase 3) |
| NEW-002 | Channel protocol cleanup (BC-060) | Fix dead `inputs_dir` parameter before any 3rd adapter | High (pre-Phase 3) |
| NEW-003 | Golden run automation (`make golden-run`) | Build after GR006a; manual runs don't scale to Phase 3 fleet | Low-now, Medium-Phase-3 |

## At-a-glance — Regista

| # | Item | Position | Urgency |
|---|---|---|---|
| sub-001 | Backend contract single-source-of-truth | Defer; evidence base too narrow, 2 bugs in 260 tests | Low |
| sub-002 | Workflow composition | Defer; pain not yet felt, add linting threshold instead | Low |

## Act-now / build-small / defer

- **Act now:** 002, 003, 008, R2-001, NEW-001, NEW-002
- **Build small, soon:** 005, 006, 007, R2-003, R2-004
- **Defer with test/stub:** 001 (spec + concrete test), 004, 009-pilot, 010-instrument, R2-005 (notification + approval path)
- **Defer regista:** sub-001, sub-002
- **Defer after Phase 3:** NEW-003
