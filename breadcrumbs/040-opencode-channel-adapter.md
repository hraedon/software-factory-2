---
number: "040"
title: OpenCodeChannel adapter — invoke opencode CLI as a channel for models with generous usage limits
severity: medium
status: proposed
kind: improvement
author: opencode
date: "2026-05-08"
tags: [runner, channel-opencode, stage-3, stage-5]
related: ["039"]
---

## Problem

Golden run 003 proved the pipeline infrastructure works end-to-end. The remaining failures are prompt quality, not architecture. To iterate on prompt quality efficiently we need to run many invocations without hitting Claude's usage limits. The factory currently only has `ClaudeCodeChannel` (spec §5 lists six channels; Phase 3 adds fleet; but we need an opencode channel now for prompt iteration velocity).

The opencode CLI (`opencode run`) provides headless non-interactive invocation of 71+ models across multiple providers (fireworks-ai, ollama-cloud, zai-coding-plan, mac-studio-lms, local free-tier models). Several models have generous or unlimited usage limits, making them ideal for rapid prompt iteration cycles.

## Proposed Implementation

### New file: `src/factory/opencode_channel.py`

Implements the `Channel` protocol from `channel.py`:

```python
class OpenCodeChannel:
    def __init__(self, config: FactoryConfig):
        ...

    @property
    def name(self) -> str:
        return "opencode"

    @property
    def family(self) -> str:
        # derive from model string prefix (e.g. "fireworks-ai" → "fireworks")
        ...

    def invoke(self, role, prompt, inputs_dir, outputs_dir, timeout) -> InvocationResult:
        ...
```

### Invocation pattern

```
opencode run --model <provider/model> --dangerously-skip-permissions <prompt_text>
```

Key flags:
- `--model <provider/model>`: model selection (e.g. `ollama-cloud/deepseek-v4-pro`, `zai-coding-plan/glm-5.1`, `opencode/nemotron-3-super-free`)
- `--dangerously-skip-permissions`: non-interactive mode, auto-approve tool use
- `--dir <outputs_dir>`: working directory for the invocation

### Output extraction

Reuse `_extract_artifact_from_output` and `_extract_json_from_output` from `claude_code_channel.py`. These are model-agnostic extraction functions (regex for fenced code blocks, JSON extraction). Extract to a shared `factory/output_extraction.py` module.

### Config integration

Add `channel: opencode` as a valid channel name in `RoleConfig`. The runner's `main()` currently hardcodes `ClaudeCodeChannel`:

```python
# current: runner.py main()
from factory.claude_code_channel import ClaudeCodeChannel
channel = ClaudeCodeChannel(config)
```

Change to a channel factory:

```python
def _create_channel(config: FactoryConfig) -> Channel:
    channels = set(rc.channel for rc in config.roles)
    if len(channels) == 1:
        ch = channels.pop()
        if ch == "opencode":
            from factory.opencode_channel import OpenCodeChannel
            return OpenCodeChannel(config)
        if ch == "claude-code":
            from factory.claude_code_channel import ClaudeCodeChannel
            return ClaudeCodeChannel(config)
    # multi-channel: return a dispatching channel
    ...
```

For Phase 2 single-channel mode, all roles use the same channel so a single channel instance suffices.

### Model selection

The `model` field in `RoleConfig` (added in this session for `--model sonnet`) maps directly to opencode's `--model` flag. Example config:

```yaml
roles:
  - role: interface_architect
    channel: opencode
    model: ollama-cloud/deepseek-v4-pro
    timeout_seconds: 600
  - role: test_author
    channel: opencode
    model: zai-coding-plan/glm-5.1
    timeout_seconds: 600
  - role: implementer
    channel: opencode
    model: fireworks-ai/accounts/fireworks/models/deepseek-v4-pro
    timeout_seconds: 600
```

This enables per-role model selection without code changes.

### Error handling

Same pattern as `ClaudeCodeChannel`:
- `TimeoutExpired` → `InvocationResult(success=False, timed_out=True)`
- `FileNotFoundError` → "opencode not found in PATH"
- Non-zero exit → capture stderr
- Empty output → "Empty output from opencode"
- cannot_proceed detection → same JSON extraction

### Family derivation

Parse the model string prefix for `family`:
- `zai-coding-plan/*` → `"zai"`
- `ollama-cloud/*` → `"ollama"`
- `fireworks-ai/*` → `"fireworks"`
- `opencode/*` → `"opencode-free"`
- `mac-studio-lms/*` → `"local-lms"`

Family is used for telemetry grouping (spec §10).

## Location

- `src/factory/opencode_channel.py` — new file, ~100 lines (heavily parallels ClaudeCodeChannel)
- `src/factory/output_extraction.py` — new file, extracted shared extraction functions
- `src/factory/claude_code_channel.py` — import extraction functions from shared module
- `src/factory/runner.py:main()` — channel factory instead of hardcoded import
- `src/factory/config.py` — no changes needed (already supports `channel` and `model` fields)
- `tests/test_opencode_channel.py` — new test file

## Exit Criteria

- `opencode run` invoked headlessly with correct model and prompt
- Output extraction works for at least 3 different provider families
- Config `channel: opencode` routes to OpenCodeChannel
- Unit tests pass (mocked subprocess)
- Integration test: one item through the pipeline with a free-tier model
- No regressions in existing tests
