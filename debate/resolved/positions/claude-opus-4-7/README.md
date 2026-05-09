# Positions — claude-opus-4-7

Independent positions on `debate/NNN-*.md` items, authored 2026-05-09 by claude-opus-4-7. Kept in this subfolder to avoid contaminating the original debate items before parallel review by Gemini, GLM-5.1, and DeepSeek-V4-Pro.

Each file `NNN.md` corresponds to `debate/NNN-*.md`.

## At-a-glance

| # | Item | Position | Urgency |
|---|---|---|---|
| 001 | Behavioral / Playwright gate | Defer to Phase 5; draft spec section now | Low (now), High (Phase 5) |
| 002 | Telemetry data quality (BC-068) | **Hard-block Phase 3** | Immediate |
| 003 | Channel adapter dedup (`SubprocessChannel`) | Refactor before 3rd adapter, conservative base | High (pre-Phase 3) |
| 004 | Pipeline checkpoints | Defer; keep design sketch | Low |
| 005 | Mutation testing | Accept; build before Phase 4 jury | Medium (Phase 3→4) |
| 006 | Per-project venv | Accept, narrow: 50-line shim, no `VenvManager` class | Medium (pre-Phase 5) |
| 007 | Credential management | Accept schema; reject rotation/audit machinery | Medium (pre-Phase 3) |
| 008 | Adversarial fixture (cert-watch GR006a) | Accept; run before Phase 2 close | Immediate |
| 009 | Event schema evolution | Accept consumer-level pilot; reject substrate registry | Medium |
| 010 | Event log retention | Defer; instrument with metrics + auto-breadcrumb threshold | Low |

## Act-now / build-small / defer-with-stub

- **Act now:** 002, 003, 008
- **Build small, soon:** 005, 006, 007
- **Defer with stub:** 001, 004, 009-pilot, 010-instrument
