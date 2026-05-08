---
number: "041"
title: _create_channel factory counts deterministic gate-channel as a second channel
severity: high
status: in_progress
kind: bug
author: opencode
date: "2026-05-08"
tags: [runner, channel-opencode]
related: ["040"]
---

## Problem

`runner.py:_create_channel()` iterates over `config.roles` to build the set of distinct channel names. The default `FactoryConfig` includes:

```python
roles = (
    RoleConfig(role="interface_architect", channel="claude-code"),
    RoleConfig(role="mechanical_gate", channel="code"),
)
```

This produces `channels = {"claude-code", "code"}` → `len(channels) == 2`, which hits the multi-channel `NotImplementedError`. Running `python -m factory.runner` with no config (or any Phase 1/Phase 2 single-model-channel config) crashes on startup.

## Root Cause

The `mechanical_gate` role binds to `channel="code"`, which is a sentinel for deterministic evaluation (the gate process does not invoke a model). `_create_channel()` should only consider non-deterministic channels when deciding which adapter to instantiate.

## Fix

Filter out `channel="code"` from the set before the length check:

```python
channels = set(rc.channel for rc in config.roles if rc.channel != "code")
```

## Location

- `src/factory/runner.py:_create_channel`

## Exit Criteria

- `python -m factory.runner` with default config (no YAML) starts without raising
- Phase 1 config (`channel="claude-code"`) starts without raising
- Phase 2 config (`channel="opencode"`) starts without raising
