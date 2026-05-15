---
number: "160"
title: "ClaudeCodeChannel has unused local alias re-exports"
severity: low
status: resolved
kind: bug
author: agent
date: "2026-05-15"
tags: [channel-claude, dead-code]
related: []
---

## Summary

`claude_code_channel.py:13-14` creates local aliases for two imported functions, but neither alias is ever referenced anywhere in the file. The class `ClaudeCodeChannel` inherits from `SubprocessChannel` and never uses `_extract_artifact_from_output` or `_extract_json_from_output`.

```python
# claude_code_channel.py:10-14
from factory.output_extraction import extract_artifact_from_output, extract_json_from_output

_extract_artifact_from_output = extract_artifact_from_output  # unused
_extract_json_from_output = extract_json_from_output          # unused
```

These appear to be leftovers from before the `SubprocessChannel` base class consolidation (BC-061, Session 19), when `ClaudeCodeChannel` had its own `invoke()` method that used these directly.

## Impact

Minimal — unused variables that add noise and could confuse maintainers. Neither alias is exported from the module or used by any other module.

## Fix

Remove the unused aliases and potentially the imports if `SubprocessChannel` provides the extraction methods.
