---
number: "019"
title: "Channel failure modes untested — timeout, non-zero exit, extraction failure"
severity: high
status: proposed
kind: bug
author: test-audit
date: "2026-05-07"
tags: [runner, channel, stage-1, tests]
---

## Background

Every test that exercises `process_work_item` uses a channel that always returns `success=True` or specifically `cannot_proceed`. The paths for:

- Timeout (`timed_out=True`)
- Non-zero exit code from claude
- Empty output
- Could not extract artifact

are handled by `_handle_invoke_failure` at `runner.py:204-243`. The non-cannot_proceed path (lines 238-243) just logs and releases the claim — the work item quietly returns to `new` with no diagnostic event. A bug in this path (wrong state, missing release, etc.) would be undetected.

## Acceptance criteria

- A test using a `FailingChannel` that returns `InvocationResult(success=False, error_message="Timeout after 600s", timed_out=True)`, then asserts: (a) the claim is released, (b) the work item is back in `new` state.
- A test for non-zero exit code failure.
- Consider whether silent claim release is the right behavior — the spec (§4, §6) says errors loop back to contract revision after N failures, but there's no event recording the failure for telemetry or retry budget tracking.