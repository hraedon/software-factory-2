---
number: "014"
title: "Resume path (_resume_and_submit) untested at integration level"
severity: high
status: implemented
kind: bug
author: test-audit
date: "2026-05-07"
tags: [runner, tests, stage-1]
related: ["003"]
resolution: added-tests
---

## Background

The fix in `_resume_and_submit` (passing full `artifact_path` instead of just `manifest.artifact_name`) resolves the immediate bug, but the entire resume-and-submit path in `process_work_item` (lines 138-145) has no test coverage.

No test creates a work item with a pre-existing resumable artifact in the workspace, claims it, and verifies that the resume path is taken instead of invoking the channel.

## Root cause

All existing tests create fresh work items with empty workspaces. The workspace/idempotency tests (`test_runner_idempotency.py`) test the workspace layer (finding, validating, quarantining artifacts) but never exercise the runner's integration with `find_resumable_artifact → _resume_and_submit`.

## Acceptance criteria

- A test using MockSubstrate that writes a valid artifact+manifest to the workspace, then calls `process_work_item` and asserts: (a) the channel is not invoked, (b) the work item transitions to `gating`, (c) the `artifact_path` in custom_fields is a full absolute path.
- A test that verifies the gate can find the artifact at the submitted path and transitions to `locked`.

## Fix applied (2026-05-07)

Added `tests/test_runner_resume.py` with three tests:
- `test_resumes_without_invoking_channel` — pre-seeds valid artifact+manifest, asserts channel NOT invoked, item reaches `gating`, artifact_path is absolute.
- `test_gate_finds_resumed_artifact_and_transitions_to_locked` — end-to-end resume + gate, asserts `locked`.
- `test_resume_preserves_actor_metadata` — asserts original channel/family/context_hash from manifest are preserved in submit transition event.

Also fixed `_resume_and_submit` hardcoding `role="interface_architect"` — now parameterized via `role_name`.
