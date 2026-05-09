---
number: "001"
title: "UI/UX validation first pass — a behavioral gate before the frontier judge"
author: opencode
date: "2026-05-09"
related: ["RFC-007", "RFC-008"]
---

## Context

The v2 pipeline currently validates implementations through:
1. Mechanical gates (syntax, mypy, pytest, ruff) — static/synthetic
2. Cross-family review — model reads code and tests
3. Frontier judge — multi-model jury reads code and tests
4. Outcome verification (Stage 9) — runs assembled software end-to-end

The mission-transcript from Factory (Luke / Factory) reveals that their most time-consuming and valuable validator is a **behavioral validator**: a QA engineer that spawns the application and interacts with it via computer use, filling forms, clicking buttons, verifying functional flows. Factory data shows 60% of wall-clock time is spent in validation, and the behavioral validator is what catches drift that code review misses.

## Problem

v2 has no behavioral validation story. The mechanical gates catch structural correctness but not semantic correctness. The frontier judge is reading tests and code, not running the software in a realistic environment. For line-of-business tooling (the target domain), the critical question is: *does the running software do what the AC says?* — and that requires interaction, not static analysis.

## Position

**Implement a `behavioral_gate` module that uses Playwright (or equivalent) to exercise the running application against acceptance criteria before the frontier judge is invoked.**

This should be a new gate type in `gate.py`, not a new pipeline stage. It runs after `implementation` passes mechanical gates and before `cross_family_review` / `frontier_judge`. If the behavioral gate fails, the implementation routes back to the implementer with diagnostics (screenshots, DOM state, error logs).

### Why Playwright specifically

- Purpose-built for web UI automation; aligns with likely LoB tool targets (web apps, dashboards, internal tools)
- Headless execution fits CI/automated pipeline
- Screenshot-on-failure provides rich diagnostics for implementer retry prompts
- Can be invoked via `subprocess` same as existing gates (mypy, pytest, ruff)
- Single dependency (`playwright` Python package + browser binaries)

### Alternative: generalize to "computer use"

If the target workload is not web-based, the gate could accept a `behavioral_spec` file (YAML) that describes:
- Command to launch the application
- Sequence of interactions (keystrokes, API calls, CLI commands)
- Expected observations (stdout patterns, file contents, HTTP responses)

Playwright is the first target; the gate framework should be extensible to other interaction modes.

### Why before the frontier judge

The frontier judge is expensive (multi-model, high wall-clock). Running a cheap mechanical behavioral gate first filters out implementations that "pass tests" but "don't run correctly." This is the same ordering principle as mechanical gates running before model judges.

## Prerequisites

- The spec YAML needs a new section: `behavioral_scenarios[]` per work-item, or the ACs need to be machine-parseable as interaction sequences
- The interface spec may need to declare a `launch_command` or `entrypoint`
- The test suite may need to include integration-test fixtures that the behavioral gate consumes

## Risks and mitigations

| Risk | Mitigation |
|---|---|
| Playwright browser binaries are large | Cache in `.factory/playwright/`; install once per project |
| Headless browser is flaky | Retry with backoff; quarantine flaky scenarios after N failures (v1 BC-146 pattern) |
| ACs are not structured enough for automation | Start with a small curated set of AC patterns that map to Playwright actions; expand incrementally |
| Adds significant wall-clock to pipeline | Run only after all mechanical gates pass; parallelize with readonly operations if possible |

## Blocking

Phase 5 (first real workload). Not needed for Phase 2/3/4 curated fixtures. However, if a Phase 5 workload is web-based, this gate is load-bearing for correctness.

## Next step

Add a `behavioral_gate.py` stub with a single Playwright scenario (e.g., "open page, verify title contains project name") and wire it into `evaluate_implementation()` behind a config flag. Validate on a simple FastAPI or Streamlit fixture.
