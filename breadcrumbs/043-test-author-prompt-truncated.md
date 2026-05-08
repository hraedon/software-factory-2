---
number: "043"
title: "test_author.md prompt template truncated mid-file — broken prompt delivered to every test_author invocation"
severity: critical
status: proposed
kind: bug
author: adversarial-review
date: "2026-05-08"
tags: [prompts, stage-3, test_author]
related: []
---

## Problem

`src/factory/prompts/test_author.md` is 80 lines and ends mid-code block:

```
def test_inverted_range_returns_error():
    """AC-02: end before start returns Error with INVERTED_RANGE."""
    result = parse_range("2024-01-07..2024-01-01", date(2024, 1, 5))
    assert isinstance(result, Error)
    assert result.code == ErrorCode.INVERTED_RANGE
```

No closing backtick fence, no closing text. The worked example is incomplete. Every `test_author` role invocation receives a truncated prompt template — this has affected every golden run (001, 002, 003).

The test_author role still achieved 100% gate-pass in golden runs, but the prompt quality is silently degraded. The truncation removes whatever guidance followed the worked example (likely "Quality bar" restatement, closing instructions, or additional example ACs).

## Evidence

Golden run 002 log: "15/15 test_suites locked on first attempt (100% pass rate)." Golden run 003: "12/12+ (100% of decided)." High pass rates mean the worked example is sufficient for the current fixture set, but the truncation is a latent correctness risk for more complex ACs.

## Fix

1. Verify the complete intended content (check git history or the interface_architect.md analog for expected closing section).
2. Close the code fence and add the missing closing content.
3. Consider adding a mechanical gate check: `evaluate_test_suite` doesn't validate test_author prompt template integrity.
