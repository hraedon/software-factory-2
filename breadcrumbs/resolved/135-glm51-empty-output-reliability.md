---
number: "135"
title: glm-5.1 (z.ai) returns empty output for implementer role — model reliability issue
severity: medium
status: resolved
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

## Root cause

Transient z.ai provider issue. Reproducibility investigation (May 14) showed:

1. Same prompts that failed 13/16 times during GR-024 (May 13 23:22-23:30) now succeed 16/16 times
2. The model processed for 10-62 seconds per attempt before returning exit code 0 with empty stdout — not a timeout, not tool-use routing
3. No unexpected files written in attempt directories (not opencode tool-use)
4. The invocation path is mechanically identical across models — only `--model` flag differs
5. Both simple (~100 byte) and implementer-length (~2KB) prompts failed during GR-024; both succeed now
6. Not a model capability gap — glm-5.1 produces correct output for all roles when the API is healthy

## Mitigations implemented

1. **Empty-output retry** (`subprocess_channel.py`): Configurable retry on empty stdout (default: 1 retry, 3s delay). Handles transient provider issues without substrate round-trip overhead. `FactoryConfig.empty_output_retries` and `empty_output_retry_delay_seconds` control behavior.

2. **Stderr diagnostic capture** (`subprocess_channel.py`): On empty output, stderr is saved to `raw_stderr.txt` and included (up to 500 chars) in the `InvocationResult.error_message`. Previously stderr was silently discarded, making root cause analysis impossible.

3. **New constants**: `ARTIFACT_FILENAME_RAW_STDERR` in `constants.py`.

4. **13 new tests** (`tests/test_empty_output_retry.py`): stderr capture, retry success, retry exhaustion, retry bypass on non-empty output / non-zero exit / timeout, delay verification, raw file content verification.

## Impact

- Multi-family jury with quorum=2 is structurally validated but unreliable with glm-5.1 as a juror
- Isolated role validation shows glm-5.1 works for interface_architect and test_author but not implementer
- The `model_override` infrastructure and unique juror key system work correctly; this is a model reliability issue, not a pipeline bug
- With the retry mitigation, transient z.ai issues will be absorbed without substrate overhead
