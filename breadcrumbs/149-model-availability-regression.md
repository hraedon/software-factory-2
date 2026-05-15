---
number: "149"
title: "Model availability regression — DeepSeek and GLM both dead in opencode channel"
severity: high
status: proposed
kind: bug
author: agent
date: "2026-05-15"
tags: [channel-deepseek, channel-glm, opencode, provider-health, golden-run]
related: ["135", "107"]
---

## Summary

Both `ollama-cloud/deepseek-v4-pro` and `zai-coding-plan/glm-5.1` returned "Model not found" / "Unexpected server error" on every invocation during GR-029 setup (2026-05-15). These models were validated in prior golden runs:

- GR-024 (2026-05-11): `zai-coding-plan/glm-5.1` for all roles
- GR-025 (2026-05-11): mixed K2 + glm-5.1 jury
- GR-027 (2026-05-14): K2 + `ollama-cloud/deepseek-v4-pro` dual-family jury

Today, both providers appear removed or renamed from the opencode configuration. The only validated working model is `fireworks-ai/accounts/fireworks/routers/kimi-k2p6-turbo`.

## Impact

- Multi-family jury is **unavailable** until an alternate model works.
- Golden runs are restricted to single-family K2-only, which inflates cost and prevents exercising the `jury_disagree` path.
- `agent_golden_run.py` pre-flight has no model-health check; it discovers provider death only at runtime after work items are populated.

## Evidence

```
Model not found: ollama-cloud/deepseek-v4-pro. Did you mean: deepseek-v4-pro?
Model not found: zai-coding-plan/glm-5.1. Did you mean: glm-5.1?
```

Both errors suggest the provider prefix was removed from the opencode provider registry. The `~/.config/opencode/opencode.json` only lists `fireworks-ai` and `mac-studio-lms` as active providers.

## Proposed direction

1. **Pre-flight model ping** — Add a `opencode run --model <model> --help` smoke test to `agent_golden_run.py` pre-flight. Abort if the model is not resolvable.
2. **Fallback model list** — Instead of a single `model` per role, support `model: [primary, fallback]` so the runner can try the next model on `channel_invoke_failed`.
3. **Provider re-registration** — Check if `zai-coding-plan` and `ollama-cloud` providers can be re-added to the opencode config, or if their model IDs changed.

## Not in scope

- Adding new providers (e.g. Gemini, local Ollama) — those need separate validation.
- Changing the jury architecture — this is an infrastructure issue, not a design issue.
