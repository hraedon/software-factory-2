---
number: "083"
title: "Channel base class mutable _family_override survives in invoke() — latent race condition for Phase 4+ parallel invocations"
severity: low
status: resolved
kind: bug
author: deepseek-v4-pro (adversarial review — Session 20)
date: "2026-05-11"
tags: [channel, runner, race, stage-4]
related: ["044"]
---

## Problem

BC-044 correctly identified a race condition: `_family` on channel instances was mutated during `invoke()`, creating a data race if a single channel is used for parallel invocations. The fix added `InvocationResult.family` so consumers can use per-invocation family. But the mutation itself was **not removed**:

`subprocess_channel.py:63`:
```python
self._family_override = invocation_family
```

This is set on every `invoke()` call and read by the `family` property:
```python
@property
def family(self) -> str:
    if self._family_override is not None:
        return self._family_override
    return self._DEFAULT_FAMILY
```

## Impact

For Phase 2 (sequential single-channel), this is benign — only one invocation is in flight at a time, so `_family_override` is always correct.

For Phase 4 (jury/race, parallel invocations on the same channel instance), this is a latent data race. If two goroutines/threads invoke the same channel simultaneously, the `_family_override` from one invocation could be read by the `family` property while another invocation is running, producing incorrect telemetry data.

## Proposed fix

Either:
1. **Remove `_family_override` entirely** — the `invoke()` method already captures `invocation_family` in the returned `InvocationResult`. The `family` property should only return `_DEFAULT_FAMILY` (its static, non-invocation-dependent value). This is the simplest and most correct fix.
2. **Remove the `family` property** — if no consumer reads `channel.family` during an invocation (all consumers use `InvocationResult.family`), the property is dead code and can be removed.

Audit all consumers of `channel.family` first to ensure none depend on per-invocation family from the channel object rather than from `InvocationResult.family`.

## Resolution

Applied Option 1: removed `_family_override` instance variable and its mutation from `invoke()`. The `family` property now returns `_DEFAULT_FAMILY` unconditionally. Per-invocation family is carried exclusively in `InvocationResult.family`, which is set in every code path of `invoke()`. Runner fallbacks (`invoke_result.family or channel.family`) still work correctly — the channel provides its default family as a last resort. Updated tests to reflect static family behavior.
