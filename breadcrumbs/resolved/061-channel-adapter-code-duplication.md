---
number: "061"
title: "95% code duplication between ClaudeCodeChannel and OpenCodeChannel"
severity: high
status: proposed
kind: improvement
author: adversarial-reviewer
date: "2026-05-08"
tags: [channel, channel-claude, channel-opencode, phase-3]
related: ["040", "041"]
---

## Summary

`ClaudeCodeChannel.invoke()` and `OpenCodeChannel.invoke()` are ~95% identical. They differ only in:

1. CLI binary name (`"claude"` vs `"opencode"`) and flags
2. Family derivation method (`FAMILY_ANTHROPIC` static vs `_derive_family()` from model provider)
3. Channel name constant (`CHANNEL_CLAUDE_CODE` vs `CHANNEL_OPENCODE`)

Everything else — `subprocess.run`, stdout capture, `raw_stdout.txt` write, artifact extraction via `output_extraction.py`, cannot_proceed JSON detection, error formatting, timeout handling, `artifact{ext}` naming — is duplicated verbatim.

## Risk

With 4 more channel adapters planned in Phase 3 (K2 API, GLM, DeepSeek Ollama, Gemini CLI), this duplication will multiply to 6 copies of the same logic. Any fix to artifact extraction, error formatting, or output handling requires changes in N places. This is the "string constant gravity" problem from v1, but with control flow instead of strings.

Spec §8 question 5 explicitly flags "runner complexity" as the most likely failure mode for v2. Code duplication is the primary driver of that complexity.

## Proposed resolution

Extract a shared `SubprocessChannel` base class or `run_channel_invoke()` helper that:
- Takes binary name + flags + family derivation function as constructor/call arguments
- Contains all the shared subprocess/artifact/extraction/error logic
- Each adapter is a thin wrapper: CLI args + family logic only

This should be done before Phase 3 channel adapter development, not after 6 channels exist.
