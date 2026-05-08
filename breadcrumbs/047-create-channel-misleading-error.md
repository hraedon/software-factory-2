---
number: "047"
title: "_create_channel raises 'Multi-channel dispatch not yet implemented' for unknown single channel"
severity: low
status: proposed
kind: bug
author: adversarial-review
date: "2026-05-08"
tags: [runner, channel-claude, channel-opencode]
related: ["041"]
---

## Problem

`runner.py:_create_channel()` raises `NotImplementedError("Multi-channel dispatch not yet implemented")` at line 362 as a catch-all for `len(channels) != 1`. This catches two distinct cases:

1. **Multi-channel config** (e.g., `claude-code` + `opencode`) — the error message is correct but the feature is deferred per phasing.
2. **Unknown single channel name** (e.g., `kimi-api`) — the error message is misleading. The config has one channel, but it's not `claude-code` or `opencode`.

An operator misconfiguring a single channel name gets a confusing error that suggests they're trying to use multi-channel dispatch.

## Fix

Separate the two cases: after filtering to one channel, explicitly check the known channel names and raise a distinct error for unrecognized channels (e.g., `ValueError("Unknown channel: kimi-api. Supported: claude-code, opencode")`). Keep the `NotImplementedError` only for genuine multi-channel configs.
