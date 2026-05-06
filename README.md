# Software Factory v2

Autonomous pipeline for producing functional software from a specification, targeted at line-of-business tooling that today is either built sloppily by non-developers or not built at all.

**Status:** Phase 1 — runner skeleton built, tests passing. Awaiting curated test set execution (Wave 6 exit criteria).

## Read first

- [`spec.md`](spec.md) — design spec (authoritative)
- [`AGENTS.md`](AGENTS.md) — agent orientation, conventions, workflow
- [`breadcrumbs/`](breadcrumbs/) — defects, design questions, improvements

## Architecture in one paragraph

Substrate (`/projects/substrate`) is the spine: durable claims, event-sourced state, validated transitions, replay. The factory is a substrate workflow plus a runner that invokes model channels (Claude Code headless, Kimi API, GLM, DeepSeek, Gemini) as workers and judges. Pipeline is sequential, AC-driven tests are the contract, gates are mechanical-then-frontier-jury, errors loop back to contract revision before worker retry. The principal reviews specs and outcomes, never code.

## Dependencies

- **substrate** — Phase 2 must land and stabilize. Tracking blockers in this repo's breadcrumbs as `dep-substrate-*`.
- **socratic-specification** — Stage 0 spec elaboration.
- **Model channels** — at least Claude (CC), K2, and one of {GLM, DeepSeek} for Phase 3.

## Status

Phase 0. No runner code yet. Spec is the only artifact; everything else is TBD.
