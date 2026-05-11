---
number: "107"
title: Phase 3 GR-015 uses unvalidated channel adapters
description: >
  golden-run-015-config.yaml binds to ollama-cloud/deepseek-v4-pro and
  zai-coding-plan/glm-5.1 via the opencode channel. AGENTS.md explicitly states
  these adapters exist but are "not yet validated in golden runs." Running GR-015
  will produce telemetry, but failures may be adapter-shaped rather than
  architecture-shaped, contaminating the role-placement data that is the whole
  point of Phase 3.
severity: high
status: proposed
kind: bug
author: opencode-adversarial-review
date: "2026-05-11"
tags: [channel, phase3, telemetry, validation, dep-v1-NNN]
---

## Proposed fix

Run isolated smoke tests for each unvalidated adapter (DeepSeek via opencode,
GLM via opencode, Gemini CLI) before mixing them into the first multi-channel
golden run. Only after each adapter passes a minimal prompt→artifact→gate
sequence should it be included in role-binding telemetry.

## Affected files

- `golden-run-015-config.yaml`
- `src/factory/opencode_channel.py`
- `src/factory/gemini_channel.py`
