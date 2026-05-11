---
number: "101"
title: JSON extraction regex matches invalid nested braces
description: >
  extract_json_from_output uses r"\{[\s\S]*?\}" which is not JSON-aware. It can match
  a truncated or syntactically invalid object, which then fails json.loads and
  falls through. In the worst case it may match a large nested object incorrectly.
severity: medium
status: resolved
kind: bug
author: opencode-adversarial-review
date: "2026-05-11"
tags: [channel, output-extraction, json]
---

## Proposed fix

Use a JSON parser with streaming or bracket-balance validation, or scan only
small windows. Consider using `json.JSONDecoder.raw_decode` with index tracking.

## Affected file

- `src/factory/output_extraction.py`

## Resolution

Replaced greedy regex with `json.JSONDecoder.raw_decode` scanning; handles nested braces correctly by parsing actual JSON structure.
