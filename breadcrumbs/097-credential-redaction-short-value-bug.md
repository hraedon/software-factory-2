---
number: "097"
title: credentials.py redaction logic is buggy for short values
description: >
  redact_value computes visible = min(4, len(value) - 4). For len < 4 this yields a
  negative number, and Python slicing silently drops characters. A 3-character key
  is redacted to "ab********" instead of a uniform mask. For len == 4, visible=0,
  which is inconsistent with the min(4, ...) intent.
severity: medium
status: proposed
kind: bug
author: opencode-adversarial-review
date: "2026-05-11"
tags: [credentials, telemetry, security-ux]
---

## Proposed fix

Clamp visible to max(0, min(4, len(value) - 4)) or simply show the first 4 chars
for any value >= 8 bytes, otherwise mask the entire string.

## Affected file

- `src/factory/credentials.py`
