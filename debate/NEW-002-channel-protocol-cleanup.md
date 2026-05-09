---
number: "NEW-002"
title: "Channel protocol cleanup before Phase 3"
author: deepseek-v4-pro
date: "2026-05-09"
related: ["BC-060", "003"]
---

## Context

The `Channel` protocol (`channel.py`) has a dead parameter: `inputs_dir: Path`. It is accepted in every adapter's signature but never used. BC-060 flags this as high severity, status `proposed`. Phase 3 will add K2/GLM/DeepSeek/Gemini channel adapters — all of which will copy the dead parameter into their signatures. At 6 adapters, it's 6 copies of a parameter that does nothing.

This is coupled with Debate 003 (channel adapter dedup). If the protocol is wrong, every adapter that implements it is wrong. Fix the protocol first; dedup second.

## Problem

A dead parameter on a public protocol is a trap. Every new developer (or agent) that implements `Channel` will wonder "what goes in inputs_dir?" and waste time figuring out it's nothing. If the protocol is not cleaned up before Phase 3, the dead parameter multiplies across 4+ new adapters.

## Position

**Resolve BC-060 before any 3rd channel adapter is written.** Either:

**Option A (preferred): Remove `inputs_dir` from the protocol.** The parameter was designed for a workflow where the channel reads input artifacts from a directory. In practice, all context is in the prompt string. Remove the parameter from `Channel.invoke()`, `ClaudeCodeChannel`, `OpenCodeChannel`, and `runner.py`'s invocation calls. Update the 10+ tests that pass a dummy `inputs_dir`.

**Option B: Document it as intentionally unused, add a test that asserts it's NEVER read.** Add a comment to `channel.py`: `# inputs_dir is reserved for future artifact-passing; currently unused. Do not implement logic that reads from it.` Add `test_inputs_dir_is_not_read()` that mocks `Path.iterdir()` and asserts it's never called during `invoke()`.

## Why Option A is better

- A dead parameter on a public protocol is a trap. Every new developer (or agent) that implements `Channel` will wonder "what goes in inputs_dir?" and waste time figuring out it's nothing.
- Removing it is a mechanical refactor: rename/delete, update callers, update tests. ~20 lines changed.
- If `inputs_dir` is needed later (Phase 5+ for artifact passing), re-add it with a clear contract.

## Test to add

```python
def test_channel_protocol_has_no_dead_parameters():
    """Every parameter on Channel.invoke() must be consumed by at least one adapter."""
    sig = inspect.signature(Channel.invoke)
    for name, param in sig.parameters.items():
        # Check: at least one concrete adapter uses this parameter
        assert param_is_used_by_at_least_one_adapter(name), \
            f"Parameter '{name}' on Channel.invoke() is unused by all adapters"
```

This test prevents the dead parameter from returning.

## Connection to Debate 003

The refactor should happen in this order:
1. Resolve BC-060 (this item) — clean up the protocol
2. Write the channel contract equivalency test (Debate 003)
3. Extract shared utilities via composition (Debate 003)
4. Only then add K2/GLM/DeepSeek/Gemini adapters
