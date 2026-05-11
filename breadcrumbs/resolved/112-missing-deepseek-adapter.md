---
number: "112"
title: Missing DeepSeek standalone channel adapter
description: >
  The spec and constants.py reference FAMILY_OLLAMA and DeepSeek concepts, but
  _create_channels only knows Claude, OpenCode, and Gemini. If a config ever
  references a DeepSeek channel name directly, it raises ValueError.
severity: medium
status: implemented
kind: improvement
author: opencode-adversarial-review
date: "2026-05-11"
tags: [channel, deepseek, phase3]
---

## Proposed fix

Either implement a standalone DeepSeekOllamaChannel adapter (spec §5 lists it)
or document that DeepSeek is only accessible via the opencode channel and remove
FAMILY_OLLAMA from constants if it is dead code.

## Affected files

- `src/factory/constants.py`
- `src/factory/runner.py` — `_create_channels`

## Resolution

Removed `FAMILY_OLLAMA` dead code from constants; DeepSeek is documented as accessible only via the opencode channel, not as a standalone adapter.
