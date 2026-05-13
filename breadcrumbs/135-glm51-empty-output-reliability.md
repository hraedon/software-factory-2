---
number: "135"
title: glm-5.1 (z.ai) returns empty output for implementer role — model reliability issue
severity: medium
status: proposed
kind: bug
author: agent
date: "2026-05-13"
tags: [channel-opencode, jury, stage-4, channel-glm]
related: ["134", "132"]
---

## Problem

During GR-024 (glm-5.1 isolated role validation via opencode channel), the model consistently returned empty stdout for the implementer role (6/6 attempts). The interface_architect and test_author roles eventually succeeded after intermittent empty-output retries (3-4 attempts each), but the implementer never produced output.

Direct CLI invocation of glm-5.1 with an implementer-style prompt produces correct output, suggesting the issue is prompt-length or context-dependent, not a fundamental channel incompatibility.

In GR-025 (mixed-family jury), glm-5.1 also returned empty output as a juror, contributing to jury_disagree outcomes.

## Evidence

- GR-024 workspace: `/tmp/sf2-golden-024/5ad038ba-.../attempt-0*/raw_stdout.txt` — all 0 bytes for implementer attempts 1-5, partial output (single function) on attempt 6
- GR-025 jury verdict: `"opencode-glm-5.1: Empty output from opencode"` in all verdicts
- Direct CLI test with same prompt structure succeeds: `echo '...' | opencode run --model zai-coding-plan/glm-5.1` produces correct code

## Impact

- Multi-family jury with quorum=2 is structurally validated but unreliable with glm-5.1 as a juror
- Isolated role validation shows glm-5.1 works for interface_architect and test_author but not implementer
- The `model_override` infrastructure and unique juror key system work correctly; this is a model reliability issue, not a pipeline bug

## Possible causes

1. Prompt length: implementer prompts include interface spec + test suite + dependencies + prior failures
2. Output format: glm-5.1 via opencode may produce tool-use output (file writes) instead of stdout for longer prompts
3. Rate limiting or context window issues on the z.ai provider

## Recommended investigation

- Test with progressively shorter implementer prompts to find the threshold
- Check if the `opencode` CLI handles long stdin differently for different models
- Consider adding a retry-with-truncated-context strategy for channels that produce empty output
