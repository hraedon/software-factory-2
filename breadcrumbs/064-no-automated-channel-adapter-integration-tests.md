---
number: "064"
title: "No automated channel adapter integration tests — regression detection requires full golden run"
severity: medium
status: proposed
kind: improvement
author: adversarial-reviewer
date: "2026-05-08"
tags: [channel, channel-claude, channel-opencode, phase-2]
related: ["019", "040"]
---

## Summary

`ClaudeCodeChannel.invoke()` and `OpenCodeChannel.invoke()` are **never tested with real subprocess execution**. The test matrix:

| What's tested | Where |
|---|---|
| Artifact extraction (regex parsing) | `test_claude_code_channel.py` |
| JSON extraction | `test_claude_code_channel.py` |
| Artifact extension per role | `test_claude_code_channel.py`, `test_opencode_channel.py` |
| Family derivation | `test_opencode_channel.py` |
| Channel name/properties | `test_opencode_channel.py` |
| Mock channel protocol conformance | `test_channel.py` |
| Timeout/error/failure Result values | `test_channel_failures.py` (_FailingChannel fake) |
| **Real subprocess execution with real CLI** | **NOTHING — one manual smoke test in golden-run-001** |

## Risk

- Claude CLI binary changes output format → extraction regex silently breaks
- Model upgrades change output shape → artifacts parse differently
- Channel adapter CLI flags change upstream → invocations silently fail

The only regression detection for channel adapter breakage is a full golden run, which requires Claude budget and operator time.

## Proposed

1. Add a subprocess-level smoke test that invokes `claude --version` (non-budget-consuming) to verify binary is reachable and returns expected exit code.
2. Capture a known-good Claude output (from golden-run-001 artifact) and test extraction functions against it as a golden-file test.
3. `@pytest.mark.skipif(not shutil.which("claude"), reason="claude not installed")` for CI environments without Claude.

Not a blocker for Phase 2 — golden runs serve as the integration test. Should be addressed before Phase 3 where 4 new channel adapters are added.
