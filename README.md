# Software Factory v2

Autonomous pipeline for producing functional software from a specification, targeting the segment of work that today is either (a) sloppily produced by non-developers using isolated AI tools, or (b) doesn't get built at all because engaging a developer costs too much.

[![Tests](https://img.shields.io/badge/tests-947%20passing-brightgreen)]()
[![Lint](https://img.shields.io/badge/lint-0%20errors-brightgreen)]()
[![License](https://img.shields.io/badge/license-MIT-blue)]()
[![Status](https://img.shields.io/badge/status-Phase%205%20active-orange)]()

This is a personal research project exploring the architecture of autonomous software development pipelines. It is developed incrementally with empirical validation via "golden runs" against curated spec fixtures. The codebase, spec, and debate records are public as evidence of structured reasoning about the problem.

**Note:** This is a research project. Issues and discussion are welcome, but active development is driven by the author's roadmap. See [`breadcrumbs/`](breadcrumbs/) for open defects and [`debate/`](debate/) for active debate.

## Read first

- [`spec.md`](spec.md) — design spec (authoritative)
- [`AGENTS.md`](AGENTS.md) — agent orientation, conventions, current status, workflow
- [`breadcrumbs/`](breadcrumbs/) — defects, design questions, improvements, RFCs, defect classes
- [`debate/`](debate/) — active architectural debate and positions
- [`workflows/MIGRATION_PLAN.md`](workflows/MIGRATION_PLAN.md) — workflow composition migration plan

## Architecture

[Substrate](https://github.com/hraedon/substrate) is the spine: durable claims, event-sourced state, validated transitions, replay, workflow composition via `extends:`. The factory is a substrate workflow plus a runner that invokes model channels (OpenCode with K2/GLM/DeepSeek model selection, Claude Code headless) as workers.

**Pipeline stages** (spec §4):
1. **Interface architect** — produces locked typed interface (.pyi)
2. **Test author** — produces pytest suite from AC + interface
3. **Implementer** — produces code that passes the tests
4. **Mechanical gates** — mypy, ruff, pytest, import checks (deterministic)
5. **Cross-family review** — different-family model reviews code against AC + interface
6. **Frontier judge (jury)** — 2–3 Tier-A models independently assess AC coverage
7. **Integration** — assembled-tree mypy, cross-module import, cross-cutting pytest
8. **Outcome verification** — end-to-end AC validation
9. **Principal review** — the only human gate

Errors loop back to contract revision, not worker retry. Gates are mechanical-first: type checkers, schema validators, test runners, and lint run before any model-judge.

## Current metrics

- **Tests:** 947 passing, 13 skipped, 0 lint errors, 0 dead code findings
- **Golden runs:** 31 executed (GR-001 through GR-031)
  - GR-031: Phase 5 validation — 17/19 locked (89%), 1st locked integration item
  - GR-027: Phase 4 exit — 30/34 locked (88%), dual-family jury (K2 + DeepSeek)
  - GR-022: Phase 4 first run — 100% lock rate (15/15)
  - GR-021: 100% lock rate (24/24), inner gate first-attempt rate 74%
- **Breadcrumbs:** 172 resolved, 1 open, 11 RFCs, 9 defect classes
- **Channel adapters:** OpenCode (K2, GLM-5.1, DeepSeek via model selection); Claude Code (stable); Gemini CLI (disabled, unvalidated)
- **Workflow composition:** phase2–5 use `extends:` inheritance from phase1 (63% line reduction)

## Dependencies

- **[substrate](https://github.com/hraedon/substrate)** — coordination and state plane. Event-sourced workflow engine with composition, replay, and validated transitions.
- **socratic-specification** — Stage 0 spec elaboration pipeline.
- **Model channels** — OpenCode (primary, multi-model), Claude Code (stable). K2 is the validated Tier-A model; GLM-5.1 and DeepSeek are validated for review/jury roles.

## Quick start

```bash
make check          # lint + audit + test (full CI gate)
make test           # pytest
make lint           # ruff check + format
make audit          # vulture dead-code check
make golden-run     # CONFIG=.factory/golden-runs/golden-run-NNN-config.yaml FIXTURES=tests/fixtures/cert-watch-mini
```

Golden runs require PostgreSQL (`docker compose -f /projects/substrate/docker-compose.test.yml up -d`) and a model channel.

## License

MIT. See [LICENSE](LICENSE).