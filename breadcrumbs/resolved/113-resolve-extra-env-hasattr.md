---
number: "113"
title: _resolve_extra_env uses unnecessary hasattr
description: >
  credentials_path is a declared dataclass field; using hasattr is defensive to
  the point of obscurity and suggests the field might not exist, which it always
  does.
severity: low
status: implemented
kind: improvement
author: opencode-adversarial-review
date: "2026-05-11"
tags: [runner, code-clarity]
---

## Proposed fix

Replace `config.credentials_path if hasattr(config, "credentials_path") else None`
with `config.credentials_path` directly.

## Affected file

- `src/factory/runner.py`

## Resolution

Removed unnecessary `hasattr` guard; `config.credentials_path` is a declared dataclass field, so the attribute always exists. Changed to `config.credentials_path` directly.
