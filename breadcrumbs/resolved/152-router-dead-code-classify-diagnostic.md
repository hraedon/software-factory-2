---
number: "152"
title: "router.py _classify_diagnostic has unreachable dead code branches"
severity: low
status: resolved
kind: bug
author: agent
date: "2026-05-15"
tags: [router, dead-code]
related: []
---

## Summary

`_classify_diagnostic()` in `router.py:50-84` has two code paths that never reach their targets:

**Path 1 (lines 51-54):** An enum-iteration loop already matches `gate_result.diagnostic_kind` against ALL `DiagnosticKind` enum values and returns early on the first match. The loop at lines 52-54 covers `cross_family_review`, `jury`, `review_malformed`, `review_found_defect`, `integration_import`, and `outcome_e2e`.

**Path 2 (lines 72-83):** Six explicit `if` checks against the same diagnostic kind strings. These are structurally unreachable — the enum loop at lines 52-54 would have already matched and returned for any of these values.

```python
# router.py:51-54 — catches ALL enum values first
if gate_result.diagnostic_kind:
    for kind in DiagnosticKind:
        if kind.value == gate_result.diagnostic_kind:
            return kind

# router.py:72-83 — unreachable dead code
if gate_result.diagnostic_kind == "cross_family_review":
    return DiagnosticKind.CROSS_FAMILY_REVIEW   # never reached
if gate_result.diagnostic_kind == "jury":
    return DiagnosticKind.JURY                   # never reached
...
```

## Impact

Minimal — dead code adds confusion for maintenance. If a new diagnostic kind is added to the enum but not to the dead-code list, the code still works (the enum loop catches it). If someone removes a value from the enum but forgets the dead-code list, there's no compiler warning.

## Fix

Remove lines 72-83. They are vestigial from before the enum-iteration loop was added.
