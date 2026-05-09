# Software Factory v2

Autonomous pipeline for producing functional software from a specification, targeting the segment of work that today is either (a) sloppily produced by non-developers using isolated AI tools, or (b) doesn't get built at all because engaging a developer costs too much.

[![Tests](https://img.shields.io/badge/tests-293%20passing-brightgreen)]()
[![License](https://img.shields.io/badge/license-MIT-blue)]()
[![Status](https://img.shields.io/badge/status-Phase%202%20active-orange)]()

This is a personal research project exploring the architecture of autonomous software development pipelines. It is developed incrementally with empirical validation via "golden runs" against curated spec fixtures. The codebase, spec, and debate records are public as evidence of structured reasoning about the problem.

**Note:** This is a research project. Issues and discussion are welcome, but active development is driven by the author's roadmap. See [`breadcrumbs/`](breadcrumbs/) and [`debate/`](debate/) for open questions and active debate.

## Read first

- [`spec.md`](spec.md) — design spec (authoritative)
- [`AGENTS.md`](AGENTS.md) — agent orientation, conventions, workflow
- [`breadcrumbs/`](breadcrumbs/) — defects, design questions, improvements, RFCs
- [`debate/`](debate/) — active architectural debate and positions

## Architecture in one paragraph

[Substrate](https://github.com/hraedon/substrate) is the spine: durable claims, event-sourced state, validated transitions, replay. The factory is a substrate workflow plus a runner that invokes model channels (Claude Code headless, OpenCode) as workers. Pipeline stages: interface_architect → test_author → implementer, with scheduler-driven handoffs between stages. AC-driven tests are the contract, gates are mechanical (mypy, pytest, ruff, import checks), errors loop back to contract revision before worker retry. The principal reviews specs and outcomes, never code.

## Current metrics

- **Tests:** 293 passing, 0 lint errors, 0 dead code findings
- **Golden runs:** 5 executed (GR001–GR005)
  - GR004 (Claude Sonnet): 12/15 implementations (80%)
  - GR005 (Kimi k2.6 via OpenCode): 13/15 implementations (87%)
- **Breadcrumbs:** 67 resolved, 8 open, 8 RFCs, 10 active debate items
- **Channel adapters:** Claude Code (stable), OpenCode (validated with real provider)
- **Pipeline:** 3-role sequential (interface_spec → test_suite → implementation)

## Dependencies

- **[substrate](https://github.com/hraedon/substrate)** — coordination and state plane. MVP + Phase 2 + Phase 3 complete.
- **socratic-specification** — Stage 0 spec elaboration pipeline.
- **Model channels** — Claude Code (primary), OpenCode (validated). K2, GLM, DeepSeek, Gemini deferred to Phase 3.

## Status

Phase 2 active. 3-stage pipeline operates with single-channel dispatch. Phase 1 exit criteria met (>90% interface_spec lock rate). Golden runs 001–005 executed with real model channels.

See `AGENTS.md`, `breadcrumbs/README.md`, and `debate/README.md` for current inventory and open issues.

## License

MIT. See [LICENSE](LICENSE).
