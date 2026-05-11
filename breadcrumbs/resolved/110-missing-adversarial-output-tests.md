---
number: "110"
title: Missing adversarial/fuzz tests for channel output parsing
description: >
  There are no tests for model output edge cases: 0 bytes, invalid UTF-8, no
  triple-backticks (falls through to heuristic), 10k lines of prose before code
  block, JSON payload with nested braces confusing the regex, or
  cannot_proceed.json with malformed JSON.
severity: medium
status: implemented
kind: improvement
author: opencode-adversarial-review
date: "2026-05-11"
tags: [tests, channel, output-extraction, robustness]
---

## Proposed fix

Add a parameterized test suite for extract_artifact_from_output and
extract_json_from_output covering the adversarial cases listed above.

## Affected files

- `tests/test_output_extraction.py` (new)
- `src/factory/output_extraction.py`

## Resolution

Added `test_output_extraction_adversarial.py` with adversarial output parsing tests covering 0 bytes, invalid UTF-8, no backticks, massive prose before code, nested JSON, and malformed cannot_proceed.
