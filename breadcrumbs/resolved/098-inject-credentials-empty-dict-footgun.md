---
number: "098"
title: inject_credentials_into_env copies full os.environ when passed empty dict
description: >
  The function signature suggests you can pass a scoped env dict, but
  `dict(env or os.environ)` means passing `{}` copies the entire parent environment.
  This is harmless today (callers pass None) but is a latent API footgun.
severity: low
status: resolved
kind: bug
author: opencode-adversarial-review
date: "2026-05-11"
tags: [credentials, api-design]
---

## Proposed fix

Change the default to None and only merge into os.environ when env is None;
otherwise merge into the provided dict without falling back to os.environ.

## Affected file

- `src/factory/credentials.py`

## Resolution

Changed default env handling: `dict(env)` only when env is explicitly provided; passing an empty dict `{}` no longer copies `os.environ` — it remains an empty dict with injected credentials.
