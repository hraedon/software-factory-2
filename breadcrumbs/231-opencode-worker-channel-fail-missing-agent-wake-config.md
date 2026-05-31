---
number: "231"
title: "GR opencode workers channel_fail — agent-wake adapter can't load config-opencode.json (stray AGENT_WAKE_CONFIG → missing file)"
severity: medium
status: implemented
kind: bug
author: claude-opus (GR-057 review session)
date: "2026-05-31"
tags: [runner, golden-run, agent-wake, opencode, channel, dev-ergonomics, run-environment]
related: ["229"]
---

## Symptom

In GR-057, opencode work item `fde76b3c` died `channel_fail` (×2 attempts),
costing a work item. `runner.log`:

```
channel_invoke_failed error="Empty output from opencode; stderr:
[agent-wake-opencode] ERR failed to start daemon client: Failed to load config
from /home/itadmin/.config/agent-wake/config-opencode.json: ENOENT: no such file
or directory, open '/home/itadmin/.config/agent-wake/config-opencode.json'"
```

(Surfaced via BC-229: the event had no `gate_name`, so telemetry first mis-binned
it as an unknown gate.)

## Root cause

`~/.config/opencode/opencode.json` loads the agent-wake opencode plugin
(`/projects/agent-wake/adapters/opencode/dist/index.js`). Its config loader
(`adapters/opencode/src/config.ts`) resolves
`path || process.env.AGENT_WAKE_CONFIG || ~/.config/agent-wake/config.json`.
**`AGENT_WAKE_CONFIG` is exported in the login environment pointing at
`~/.config/agent-wake/config-opencode.json` — a per-harness config that was
never created** (only `config.json` exists). So `loadConfig` throws ENOENT on
every opencode worker. This is the "stray `AGENT_WAKE_CONFIG`" harness-wiring
gotcha made concrete.

## Fix (applied — environment, not repo)

Created `~/.config/agent-wake/config-opencode.json` (the intended per-harness
config): `version: 1`, `socket_path: null`, one opencode source. Verified it
satisfies `config.ts::loadConfig` (version ∈ {0,1}, ≥1 source) and that the load
path no longer ENOENTs.

## Residuals — why status is `implemented`, not `resolved`

1. **GR-confirmation pending.** The adapter's `ensureClientStarted` *catches* the
   config error and degrades (does not re-throw), yet the worker still emitted
   **empty output** → `channel_fail`. So either the config ENOENT was the
   proximate cause (most likely — it was the only stderr error) or it correlates
   with another empty-output cause. Confirm on the next GR that opencode workers
   no longer `channel_fail`. If they still do, the deeper fix is in the adapter:
   **a non-essential wake-config/daemon failure must never surface as worker
   output failure** (isolate the plugin's stderr/exit from the worker's task).
2. **Reproducibility gap (ties to the provenance thesis).** This fix is
   environment state (`~/.config/...`), not captured in any repo — it won't
   survive an environment rebuild. The agent-wake opencode config provisioning
   (and/or the source of the `AGENT_WAKE_CONFIG` export) should be captured in
   agent-wake setup or sf2 run-env docs so GR environments are reproducible.

## Why this isn't the previous fix recurring

First instance of this defect shape (run-env harness-wiring config gap). Related
to BC-229 only as the upstream cause of that telemetry symptom.
