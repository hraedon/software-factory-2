---
number: "007"
title: "Integration tests are stubs — don't validate runner or gate behavior"
severity: medium
status: proposed
kind: bug
author: opencode
date: "2026-05-06"
tags: [runner, gate]
related: ["002", "006"]
---

## Problem

The three integration test classes (`TestRunnerSmoke`, `TestGateProcessIntegration`) don't actually exercise the runner or gate process functions. They create regista work items and then assert trivially true conditions without calling `process_work_item()` or `process_gate_item()`.

### `TestRunnerSmoke.test_full_loop_with_mock_channel`

Creates a work-item, creates a `FakeChannel()` (which is never used), registers an actor role, and returns. No assertions about runner behavior.

### `TestRunnerSmoke.test_workspace_artifacts_written`

Tests workspace write + `find_resumable_artifact` round-trip. This is a workspace test, not a runner test. The same scenario is covered by `test_workspace.py`.

### `TestGateProcessIntegration.test_gate_process_passes_valid_artifact`

Creates a work-item, manually transitions it through `claim` and `submit`, then asserts `work_item_type == "interface_spec"` (trivially true). Never calls `process_gate_item()`.

## Why this matters

These tests give false confidence. They pass green (including in the 59-test count from session 3) but validate nothing about the runner or gate process. The actual end-to-end path (`new → in_progress → gating → locked`) has never been tested programmatically.

## Dependencies

- BC-006 (MockSubstrate) would enable testing this without Postgres.
- Kimi is currently working on completing the end-to-end smoke test, which should address this gap.

## Acceptance criteria

- [ ] A test exists that calls `process_work_item()` end-to-end with a mock channel and asserts the work-item reaches `gating`.
- [ ] A test exists that calls `process_gate_item()` end-to-end with a valid artifact and asserts the work-item reaches `locked`.
- [ ] A test exists that calls `process_gate_item()` with an invalid artifact and asserts `gate_fail` with correct diagnostics.
- [ ] The stub tests in `test_runner_smoke.py` and `test_gate_process.py` are either replaced or extended with real assertions.
