---
number: "RFC-003"
title: "Channel adapter auth-mode detection — v1 BC-376 shows env var injection breaks native auth"
severity: high
status: proposed
kind: design
author: adversarial-review
date: "2026-05-08"
tags: [channel-opencode, channel-claude, channel-glm, channel-deepseek, dep-v1-376]
related: ["040", "044"]
---

## Problem

v1's BC-376: `OpenCodeProvider.launch()` unconditionally injected `OPENAI_BASE_URL=https://api.fireworks.ai/inference/v1` and `OPENAI_API_KEY` into the subprocess environment. When the model was a native provider (`zai-coding-plan/glm-5.1`), these env vars overrode the native auth, causing the agent to exit with return code 0 but do zero work. Silent kill: no error surfaced until `.kickoff-status` was found missing.

v2's channel adapters will invoke models through different harnesses:
- `ClaudeCodeChannel` → `claude --print` (Anthropic API key in env, no passthrough needed)
- `OpenCodeChannel` → `opencode run --model <provider/model>` (native prefixes handle their own auth)
- Future: `KimiAPIChannel` → API key auth
- Future: `GLMChannel` → z.ai auth
- Future: `GeminiCLIChannel` → Google Cloud auth

Each adapter has its own auth model. The `OpenCodeChannel` currently passes `--model zai-coding-plan/glm-5.1` which should use z.ai's native auth — but if any env var injection gets added later (for non-native models), it could override and create the exact v1 BC-376 bug.

## Proposal

Define an auth contract in the `Channel` protocol:
1. Each channel adapter declares `auth_mode: "native" | "passthrough" | "api_key"`.
2. Native providers receive no env var injection — they manage their own credentials.
3. Passthrough providers receive explicit `OPENAI_BASE_URL` + `OPENAI_API_KEY` (or equivalent).
4. The channel adapter factory validates that the model's provider prefix is compatible with the auth mode before launch.

## Dependencies

Awaits Phase 3 when multi-channel adapters are built. The auth-mode distinction should be part of the channel adapter interface from the first non-Claude adapter.
