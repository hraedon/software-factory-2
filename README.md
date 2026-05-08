# Software Factory v2

Autonomous pipeline for producing functional software from a specification, targeted at line-of-business tooling that today is either built sloppily by non-developers or not built at all.

**Status:** Phase 2 — sequential single-channel pipeline validation. 259 tests, 2 channel adapters, 3 golden runs executed.

## Read first

- [`spec.md`](spec.md) — design spec (authoritative)
- [`AGENTS.md`](AGENTS.md) — agent orientation, conventions, workflow
- [`breadcrumbs/`](breadcrumbs/) — defects, design questions, improvements, RFCs

## Architecture in one paragraph

Substrate (`/projects/substrate`) is the spine: durable claims, event-sourced state, validated transitions, replay. The factory is a substrate workflow plus a runner that invokes model channels (Claude Code headless, OpenCode) as workers. Pipeline stages: interface_architect → test_author → implementer, with scheduler-driven handoffs between stages. AC-driven tests are the contract, gates are mechanical (mypy, pytest, ruff, import checks), errors loop back to contract revision before worker retry. The principal reviews specs and outcomes, never code.

## Dependencies

- **substrate** — `/projects/substrate`, editable install. Phase 2 stable; sufficient for current pipeline.
- **socratic-specification** — Stage 0 spec elaboration.
- **Model channels** — Claude Code (primary), OpenCode (stub). K2, GLM, DeepSeek, Gemini deferred to Phase 3.

## Status

Phase 2 active. 3-stage pipeline (interface_spec → test_suite → implementation) operates with single-channel dispatch. Phase 1 exit criteria met (>90% interface_spec lock rate). Golden runs 001-003 executed; 004 pending after critical breadcrumb resolution.

See `AGENTS.md` and `breadcrumbs/README.md` for current inventory and open issues.
