---
number: "163"
title: "agent_golden_run.py danger signal checks have duplicate unreachable code blocks"
severity: low
status: resolved
kind: bug
author: agent
date: "2026-05-15"
tags: [golden-run, dead-code]
related: []
---

## Summary

`_monitor_logs()` in `agent_golden_run.py:302-332` has two identical blocks of fatal checks. Lines 305-321 and lines 322-332 are exact duplicates. The second block is unreachable because the first block already handles all conditions (with `_fatal()` which calls `sys.exit(1)`).

```python
# agent_golden_run.py:305-321 — first block
if name == "claim_near_budget" and count >= 5:
    _fatal(...)
if name in ("gate_fail_cross_family_review", "gate_fail_jury") and count >= 3:
    _fatal(...)
if name == "channel_invoke_failed" and count >= 5:
    _fatal(...)

# agent_golden_run.py:322-332 — exact duplicate, unreachable
if name in ("gate_fail_cross_family_review", "gate_fail_jury") and count >= 3:
    _fatal(...)  # never reached
if name == "channel_invoke_failed" and count >= 5:
    _fatal(...)  # never reached
```

## Impact

Minimal — dead code adds confusion. If a future edit changes the threshold in one block but not the other, the behavior won't change (the second block is dead), but maintainers may be misled.

## Fix

Remove lines 322-332.
