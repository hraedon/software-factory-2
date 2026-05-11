---
number: "098"
title: inject_credentials_into_env copies full os.environ when passed empty dict
description: >
  The function signature suggests you can pass a scoped env dict, but
  `dict(env or os.environ)` means passing `{}` copies the entire parent environment.
  This is harmless today (callers pass None) but is a latent API footgun.
severity: low
status: proposed
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
