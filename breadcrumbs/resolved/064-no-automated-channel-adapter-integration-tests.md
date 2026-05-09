---
number: "064"
title: "No automated channel adapter integration tests — regression detection requires full golden run"
severity: medium
status: resolved
kind: improvement
author: adversarial-reviewer
date: "2026-05-08"
tags: [channel, channel-claude, channel-opencode, phase-2]
related: ["019", "040"]
---

## Summary

`ClaudeCodeChannel.invoke()` and `OpenCodeChannel.invoke()` were **never tested with real subprocess execution**. The test matrix:

| What's tested | Where |
|---|---|
| Artifact extraction (regex parsing) | `test_claude_code_channel.py` |
| JSON extraction | `test_claude_code_channel.py` |
| Artifact extension per role | `test_claude_code_channel.py`, `test_opencode_channel.py` |
| Family derivation | `test_opencode_channel.py` |
| Channel name/properties | `test_opencode_channel.py` |
| Mock channel protocol conformance | `test_channel.py` |
| Timeout/error/failure Result values | `test_channel_failures.py` (_FailingChannel fake) |
| **Real subprocess execution with real CLI** | **NOTHING** |

## Risk

- Claude CLI binary changes output format → extraction regex silently breaks
- Model upgrades change output shape → artifacts parse differently
- Channel adapter CLI flags change upstream → invocations silently fail

The only regression detection for channel adapter breakage was a full golden run, which requires Claude budget and operator time.

## Resolution

Added `tests/test_channel_integration.py` with three test classes:

1. **`TestClaudeSmokeTest`** — `claude --version` and `claude --help` subprocess reachability tests (skip if `claude` not in PATH)
2. **`TestOpenCodeSmokeTest`** — `opencode --help` subprocess reachability test (skip if `opencode` not in PATH)
3. **`TestGoldenFileExtraction`** — golden-file tests against known-good output from `golden-run-001` fixtures:
   - `test_fixtures_directory_exists` — verifies fixture data is present
   - `test_extract_interface_spec_artifact` — `extract_artifact_from_output` extracts code from real `.pyi` output
   - `test_extract_interface_spec_matches_file` — extracted content matches saved `artifact.pyi`
   - `test_cannot_proceed_extraction` — `extract_json_from_output` parses real `cannot_proceed` JSON
   - `test_cannot_proceed_matches_file` — extracted JSON matches saved `cannot_proceed.json`
   - `test_all_interface_spec_fixtures_extractable` — every fixture in golden-run-001 round-trips through extraction
4. **`TestChannelInvokeWithGoldenOutput`** — end-to-end channel processing pipeline tests:
   - `test_claude_channel_processes_interface_spec_output` — full extraction → file write pipeline for interface_spec
   - `test_claude_channel_processes_cannot_proceed_output` — full JSON → file write pipeline for cannot_proceed

Total: 11 new tests. 293 tests pass, 0 lint errors, 0 audit findings.