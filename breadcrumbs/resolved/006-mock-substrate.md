---
number: "006"
title: "MockSubstrate needed for CI-portable tests"
severity: medium
status: resolved
kind: improvement
author: opencode
date: "2026-05-06"
tags: [runner, telemetry]
related: ["002"]
---

## Problem

Three integration tests (in `test_runner_smoke.py`, `test_gate_process.py`, and one in the original wave-5 delivery) require a live Postgres instance with substrate installed. These tests are marked `@pytest.mark.integration` and are skipped in CI environments without Postgres.

The plan calls for `MockSubstrate` in Wave 6 golden-run testing (BC-002 §"New acceptance criteria from v1 lessons"): "A golden-run test runs the full `runner.py` loop with `MockChannel` + `MockSubstrate` and produces the same sequence of transitions."

Without `MockSubstrate`, the runner and gate process cannot be tested end-to-end in CI. The current "integration" tests are also stubs (see BC-007 for the test quality gap) — they create work items but don't exercise the actual process functions.

## Proposal

Build a `MockSubstrate` in `tests/_mock_substrate.py` that:
1. Implements the same interface as `substrate.Substrate` used by the runner and gate process (`create_work_item`, `transition`, `acquire_claim`, `release_claim`, `read_events`, `query_work_items`, `get_work_item`, `register_actor_role`).
2. Stores state in memory (dicts/lists).
3. Produces the same event shapes as real substrate for `derive_failures()` and `derive_context()`.
4. Is wired into `conftest.py` as an alternative to the live substrate fixture.

This is not a substrate replacement — it is a test double scoped to the factory's usage of substrate's API.

## Acceptance criteria

- [ ] `MockSubstrate` supports all substrate methods used by `runner.py` and `gate_process.py`.
- [ ] `derive_failures()` works with `MockSubstrate` event storage.
- [ ] `derive_context()` works with `MockSubstrate` work-item lookups.
- [ ] End-to-end runner + gate process test runs without Postgres using `MockSubstrate` + `MockChannel`.
- [ ] All existing integration tests have `MockSubstrate` equivalents that run in CI.
