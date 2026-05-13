---
number: "108"
title: GeminiCLIChannel exists but is essentially untested in production
description: >
  The adapter is a 29-line thin wrapper with no golden-run validation. The spec
  notes Gemini-cli flakiness is "largely harness-shaped." Shipping an untested
  adapter in the channel factory is a reliability risk.
severity: medium
status: implemented
kind: bug
author: opencode-adversarial-review
date: "2026-05-11"
tags: [channel, gemini, phase3, validation]
related: ["107"]
---

## Proposed fix

Execute at least one isolated golden-run smoke test with GeminiCLIChannel on a
single work-item before relying on it in any multi-channel config.

## Affected file

- `src/factory/gemini_channel.py`
