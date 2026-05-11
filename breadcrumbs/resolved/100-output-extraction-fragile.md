---
number: "100"
title: Output extraction regex is fragile and easily gamed
description: >
  extract_artifact_from_output uses a greedy-ish regex on triple-backticks. If a
  model emits multiple fenced blocks, the regex may capture the wrong one. The
  fallback heuristic (from/import/class/def/#) can extract prose containing those
  words. There is no size limit, so a 10 MB explanation before code causes a full
  regex scan.
severity: medium
status: resolved
kind: bug
author: opencode-adversarial-review
date: "2026-05-11"
tags: [channel, output-extraction, robustness]
---

## Proposed fix

1. Prefer the last ```python block, not the first.
2. Cap the fallback heuristic to the first N lines after the last code fence.
3. Add a max-size truncation before regex scanning.

## Affected file

- `src/factory/output_extraction.py`

## Resolution

Updated `extract_artifact_from_output` to prefer the last `python` block, then last any-language block, with fallback heuristic limited to 200 lines.
