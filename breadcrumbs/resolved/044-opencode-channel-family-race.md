---
number: "044"
title: "OpenCodeChannel mutates self._family on invoke() — race condition corrupts telemetry"
severity: high
status: resolved
kind: bug
author: adversarial-review
date: "2026-05-08"
tags: [channel-opencode, telemetry, runner]
related: ["040"]
---

## Problem

`opencode_channel.py:71` mutates `self._family` during `invoke()`:

```python
if role_config and role_config.model:
    self._family = _derive_family(role_config.model)
```

This is an instance-level mutable attribute set during invocation. If two workers share a channel object for different roles with different models, concurrent invocations will corrupt each other's telemetry metadata. The runner reads `channel.family` *after* `invoke()` returns (runner.py:225-231) for `ActorMetadata` — so a slow invocation from one role can pick up the family derived from a fast invocation for a different role.

The spec's Principles 10 and 11 depend on per-role per-channel telemetry for model placement decisions. Corrupted family metadata silently produces wrong pass-rate tables, which drives wrong channel-binding decisions.

## Fix

`family` should be derived per-invocation, not stored as instance state. The `family` property exists for the `Channel` protocol's `name`/`family` attributes, but invoke should return the per-invocation family in `InvocationResult` or the runner should derive it from the role config directly.
