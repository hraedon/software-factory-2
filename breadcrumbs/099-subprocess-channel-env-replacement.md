---
number: "099"
title: SubprocessChannel.invoke replaces entire child environment
description: >
  When extra_env is not None, subprocess.run(..., env=env_override) replaces the
  child environment entirely. The caller (inject_credentials_into_env) mitigates
  this by copying os.environ first, but the channel layer does not enforce or
  document this contract. A future adapter passing a partial dict silently breaks
  PATH and other required env vars.
severity: medium
status: proposed
kind: design
author: opencode-adversarial-review
date: "2026-05-11"
tags: [channel, subprocess, env, api-design]
---

## Proposed fix

Document in Channel protocol that extra_env is merged into the parent
environment, not a replacement. In SubprocessChannel, merge explicitly:
`env={**os.environ, **(extra_env or {})}` instead of passing env_override raw.

## Affected file

- `src/factory/subprocess_channel.py`
- `src/factory/channel.py` (protocol docstring)
