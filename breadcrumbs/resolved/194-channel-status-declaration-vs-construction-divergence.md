---
number: "194"
title: Channel status declaration vs. constructor divergence — GLM/DeepSeek/Gemini constructible despite "disabled"/"unvalidated" status
severity: high
status: implemented
kind: defect-class
author: claude
date: "2026-05-19"
tags: [channel-glm, channel-deepseek, channel-gemini, rfc, stage-3]
related: ["RFC-037"]
---

## Summary

AGENTS.md declares GLM-5.1, DeepSeek, and Gemini channels as unvalidated and/or disabled, but the channel registry in `src/factory/runner.py` constructs `gemini-cli` unconditionally and `opencode` (the access path for GLM-5.1 and DeepSeek via model selection) with no awareness of the declared status. A new caller selecting any of these in a config silently gets a working constructor; the prose declaration in AGENTS.md is unenforced.

The same gap is identified by debate item `adversarial-readiness-001` (critique #2): "Three of five configurable channels are unviable or unvalidated… they will silently fail if a config ever selects them." RFC-037 ("detect → enforce → retire tiering") names this exact case as its lead worked example.

## Evidence

### Declared status (AGENTS.md, canonical)

- AGENTS.md:50 — "3 channel adapters: ClaudeCodeChannel, OpenCodeChannel (K2/GLM/DeepSeek via model selection); GeminiCLIChannel disabled (unvalidated)"
- AGENTS.md:107 — "Channel adapters for DeepSeek (standalone Ollama adapter) and Gemini exist but are not yet validated in golden runs."
- AGENTS.md:78 — "All validated channels have working adapters; unvalidated adapters disabled." (claim contradicted by the constructor)

### Constructor (no enforcement)

`src/factory/runner.py:1120-1153`:

```python
_CHANNEL_CONSTRUCTORS: dict[str, type[Channel]] = {}

def _register_channel(channel_name: str, import_path: str, class_name: str) -> None:
    import importlib
    _CHANNEL_CONSTRUCTORS[channel_name] = getattr(importlib.import_module(import_path), class_name)

_register_channel(CHANNEL_OPENCODE, "factory.opencode_channel", "OpenCodeChannel")
_register_channel(CHANNEL_CLAUDE_CODE, "factory.claude_code_channel", "ClaudeCodeChannel")
_register_channel(CHANNEL_GEMINI_CLI, "factory.gemini_channel", "GeminiCLIChannel")

def _create_channels(config: FactoryConfig) -> dict[str, Channel]:
    channel_names = set(rc.channel for rc in config.roles if rc.channel != CHANNEL_CODE)
    channels: dict[str, Channel] = {}
    for ch_name in channel_names:
        constructor = _CHANNEL_CONSTRUCTORS.get(ch_name)
        if constructor is None:
            raise ValueError(f"Unknown channel: {ch_name}. Supported: {_SUPPORTED_CHANNEL_NAMES}")
        channels[ch_name] = constructor(config)
    ...
```

- `gemini-cli` is registered unconditionally despite being declared "disabled (unvalidated)".
- GLM-5.1 and DeepSeek are routed through `opencode` via `RoleConfig.model`; the constructor sees only the channel name and has no view of the model-level validation status. A config setting `model: glm-4.6` on the opencode channel constructs without warning and runs straight into the GR-017 failure mode (BC-149).
- Spec §5's channel/capability table likewise lists these as available with no "validated" column.

### Consequence

There is no single point at which a config that selects an unvalidated channel or model is refused or warned. The declared status lives only in prose. Any new caller (agent, principal, or fresh contributor) reading the spec table or the constructor sees an apparently-available channel.

## Proposed fix (per RFC-037 worked example)

Introduce a `CHANNEL_STATUS` map (or equivalent declaration adjacent to `_register_channel`) keyed by channel name, with values from `{"validated", "unvalidated", "disabled"}`. `_create_channels` consults it before constructing:

```python
# tier: enforce
# precondition: AGENTS.md "channel status" table is the source of truth
# audit trigger: re-evaluate when any channel moves between validated/unvalidated/disabled
CHANNEL_STATUS: dict[str, str] = {
    CHANNEL_OPENCODE:    "validated",
    CHANNEL_CLAUDE_CODE: "validated",
    CHANNEL_GEMINI_CLI:  "disabled",
}

def _create_channels(config: FactoryConfig) -> dict[str, Channel]:
    ...
    for ch_name in channel_names:
        status = CHANNEL_STATUS.get(ch_name)
        if status == "disabled":
            raise ChannelDisabled(f"channel {ch_name} is disabled; see AGENTS.md")
        if status == "unvalidated":
            warnings.warn(f"channel {ch_name} is unvalidated; see AGENTS.md", stacklevel=2)
        channels[ch_name] = constructor(config)
```

For GLM/DeepSeek (model-level, not channel-level) the same shape applies at the model layer: a `MODEL_STATUS` declaration that `OpenCodeChannel` (or `_create_channels`) consults when `RoleConfig.model` resolves to a known-unvalidated/disabled model snapshot.

Update spec §5 to add a "Status" column whose values are required to match `CHANNEL_STATUS` / `MODEL_STATUS` (single source of truth; the spec table is derived from code, or vice versa via a CI check — see RFC-037 §Operational cost).

## Acceptance criteria

- AC-1: `CHANNEL_STATUS` (or equivalent) is declared adjacent to `_register_channel` and covers every channel name reachable from any shipping config.
- AC-2: `_create_channels` raises a typed error (e.g., `ChannelDisabled`) when a config selects a `disabled` channel.
- AC-3: `_create_channels` emits a single `warnings.warn` (not silent log) when constructing an `unvalidated` channel.
- AC-4: Equivalent enforcement exists at the model layer for GLM-5.1 and DeepSeek when accessed via `opencode`, OR a documented decision to keep model-level status in AGENTS.md only with a `# tier: detect` comment at the construction site naming where status lives.
- AC-5: Spec §5 capability table either gains a "Status" column matching `CHANNEL_STATUS`/`MODEL_STATUS` or is cross-referenced from the constructor's audit-trigger comment.
- AC-6: Regression test: a config selecting `gemini-cli` (current status: disabled) fails to start with the typed error; a config selecting an `unvalidated` channel triggers a recorded warning.

## Defect-class shape

This is filed as `kind: defect-class` because the same shape (declared-status vs. construction-site divergence) recurs across sf2, regista, and v1 — RFC-037 catalogs four other instances. If RFC-037 is adopted, this BC becomes the worked example that drives the channel-registry tagging pass and the first audit site.

## Links

- RFC-037 — Detect → enforce → retire tiering (this BC is RFC-037's lead worked example).
- `debate/adversarial-readiness-001.md` critique #2 — independent identification of the same gap.
- BC-108 — GeminiCLIChannel disabled/removed from runner registration (closed; the constructor still imports the class but `gemini-cli` is currently the only registered channel from this group; status drift is the live issue).
- BC-149 — Model availability regression (DeepSeek/GLM dead in opencode); pre-flight model ping mitigates the runtime symptom but does not enforce declared status at construction.
- AGENTS.md lines 50, 78, 107, 239 — canonical "channel status" declarations.
- `src/factory/runner.py:1120-1153` — current `_register_channel` / `_create_channels`.
