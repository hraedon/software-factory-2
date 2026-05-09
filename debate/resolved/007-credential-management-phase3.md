---
number: "007"
title: "Credential management for Phase 3 multi-channel fleet"
author: opencode
date: "2026-05-09"
related: ["RFC-003", "BC-040", "BC-041"]
---

## Context

Phase 3 adds K2 API ($7/wk → $49/mo), GLM z.ai, DeepSeek Ollama Pro, and Gemini CLI. Today v2 runs on:
- Claude Code (subscription, headless) — no API key needed
- OpenCode (local CLI, model selected via `--model`) — provider keys managed by opencode CLI itself

But K2, GLM, and DeepSeek require explicit API keys or subscription tokens. These are not in `FactoryConfig` today. The v1 `Credentials/` folder (now gitignored in all repos) stored `fireworks.txt`, `zai.txt`, `ollama.txt`, `kubeconfig` — ad-hoc files without a schema.

## Problem

As the fleet expands, credential management becomes a operational and security bottleneck:
- **Rotation:** API keys expire or get revoked. How does the runner discover a key is stale before failing a channel invoke?
- **Isolation:** Per-project keys vs global keys? A factory project should not accidentally use the principal's personal GLM token.
- **Visibility:** The principal cannot review code, but they *can* review a credential inventory. There is no single place to see which keys are active, which are expired, and which projects use them.
- **Security:** Keys in env vars leak to subprocess gates (pytest, mypy). Keys in config files end up in git if `.gitignore` drifts.

## Position

**Add a `CredentialManager` abstraction to `FactoryConfig` with per-project, per-provider key slots, and a `credentials.yaml` schema that lives outside the repo.**

### Proposed design

1. **Schema:** `~/.config/factory/credentials.yaml`
   ```yaml
   version: 1
   providers:
     fireworks:
       api_key: "fk-..."
       expires_at: "2026-06-01"
     zai:
       api_key: "zai-..."
     ollama_pro:
       api_key: "ollama-..."
   ```

2. **FactoryConfig integration:** `credentials_path: Path | None` field. Loaded at startup, merged into `RoleConfig` as `api_key`.

3. **Channel adapter contract:** Each adapter receives `role_config` which now includes `api_key`. Adapters inject the key via env var or CLI flag as appropriate.

4. **Rotation detection:** Channel adapters return a specific `error_message` shape for auth failures (`401 Unauthorized`, `key revoked`). The runner treats these as `channel_fail` with `diagnostic_kind = "auth_error"`, routing to the scheduler for re-assignment to a different channel (fallback binding).

5. **Audit:** Telemetry captures `provider` and `key_id` (hashed) per invocation. The principal can review which providers are active without seeing keys.

### Why not env vars

Env vars are the easiest path (`FIREWORKS_API_KEY`, etc.) but:
- They leak to subprocess gates (pytest inherits env)
- They are invisible to the principal
- They don't support per-project isolation
- Rotation requires restarting the runner process

### Why not the v1 `Credentials/` folder pattern

V1 stored raw text files in a gitignored folder. No schema, no rotation, no audit. It worked for 1–2 providers but does not scale to 6+.

## Risks

| Risk | Mitigation |
|---|---|
| `credentials.yaml` outside repo is lost in host migration | Document backup requirement; keep in home dir (standard XDG) |
| Key in `RoleConfig` gets logged by structlog | Redact `api_key` field in log serialization (mask first 4 chars) |
| Per-provider key format differs (Bearer vs query param) | Channel adapter handles provider-specific injection; config stays generic |
| Principal cannot review credential file | `credentials.yaml` is human-readable YAML; no code knowledge needed |

## Blocking

Phase 3 (fleet integration). Cannot add K2/GLM/DeepSeek adapters without a key management story.

## Next step

1. Define `credentials.yaml` schema (5 lines)
2. Add `CredentialManager` class in `config.py`
3. Update `OpenCodeChannel` to read `api_key` from `RoleConfig` and inject into subprocess env
4. Add rotation detection in `_handle_invoke_failure` for HTTP 401 patterns
5. Test with a dummy key and mock channel that asserts key presence
