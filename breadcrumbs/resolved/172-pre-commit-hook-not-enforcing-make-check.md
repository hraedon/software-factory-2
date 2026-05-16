---
number: "172"
title: "Pre-commit hook does not enforce `make check` — lint errors and broken tests land in main"
severity: medium
status: resolved
kind: improvement
author: opus-4-7
date: "2026-05-16"
tags: [tooling, ci, process, hook, CLASS-014]
related: ["170", "CLASS-014"]
---

## Problem

Two recent commits landed on `main` with lint errors and/or broken tests that should have been caught by `make check`:

1. **e773a45** (Opus, 2026-05-15) — committed the BC-170 fix with 3 lint errors (2 line-length in `pre_gate.py`, 1 import-ordering E402 in `subprocess_channel.py`), 1 missing telemetry registration (`GATE_NAME_INNER_JSON_SHAPE` not in `DETERMINISTIC_GATES`), and 1 broken test API (`_cleanup_offered` signature change without updating tests).
2. Prior session with the same agent had a comparable pattern (see reflection `2026-05-16-glm-5-1-11.md`).

Cleanup landed in **92db31e**. The fix itself was correct, but downstream agents had to spend a session repairing it before continuing.

`AGENTS.md` already says to run lint/test before commit, but that's documentation, not enforcement.

## Impact

- Wasted agent sessions on cleanup that the pre-commit hook would have caught locally
- Two CLASS-014 instances (test-coverage gaps for new code) that would have been forced by the test gate
- Trust erosion: subsequent agents must defensively re-run `make check` on every commit to detect inherited breakage

## Files / Lines

- `.git/hooks/pre-commit` — verify whether it exists and what it runs
- `Makefile` — `make check` target (assumed: ruff + mypy + pytest)
- `AGENTS.md` — currently documents the expectation without enforcement

## Fix

Two options, in order of preference:

1. **Install a `pre-commit` hook that runs `make check`** (or `make lint test` with a fast subset). Fail the commit on non-zero exit. This is the standard tool-enforced answer.
2. **Pre-push hook** if pre-commit is too slow — runs the same gates but allows local WIP commits.

Whichever is chosen, the hook script should be checked into the repo (e.g., `.githooks/pre-commit`) and `make init` (or equivalent) should `git config core.hooksPath .githooks` so every clone gets it.

## Resolution

Created `.githooks/pre-commit` running `make check` (lint + audit + test). Hook is checked into the repo and `git config core.hooksPath .githooks` is set. Option (1) from the fix proposal was chosen — pre-commit enforcement, not pre-push.

## Lesson

Agents will skip steps that are documented but not enforced. The pipeline already depends on hooks (the runner's own hook queue), so the principle of "automate, don't document" is part of the project's worldview — it just hadn't been applied to commits yet.
