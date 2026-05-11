---
number: "103"
title: quarantine_attempt uses os.replace which can clobber
description: >
  If timestamp collision occurs (clock skew or very fast retries), os.replace
  silently overwrites the destination quarantine directory, losing the prior
  corrupted attempt.
severity: low
status: resolved
kind: bug
author: opencode-adversarial-review
date: "2026-05-11"
tags: [workspace, data-loss, edge-case]
---

## Proposed fix

Include subsecond/millisecond timestamp or a UUID suffix in the quarantine
destination name, or check existence and append a counter.

## Affected file

- `src/factory/workspace.py`

## Resolution

Added subsecond timestamp and collision counter to `quarantine_attempt` destination path, preventing silent overwrite of existing quarantine directories.
