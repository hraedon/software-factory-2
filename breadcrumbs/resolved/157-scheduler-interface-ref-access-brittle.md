---
number: "157"
title: "Scheduler propagate_fields access uses hardcoded index 0 instead of field name"
severity: medium
status: resolved
kind: bug
author: agent
date: "2026-05-15"
tags: [scheduler, stage-topology]
related: []
---

## Summary

`scheduler.py:153-154` accesses `propagate_fields[0]` with the implicit assumption that the first element is always the `CUSTOM_FIELD_INTERFACE_REF`. This is structurally brittle.

```python
# scheduler.py:151-158
for extra_link_type in additional_links:
    if extra_link_type == LINK_TYPE_IMPLEMENTS:
        pf = handoff.propagate_fields
        interface_ref = custom.get(pf[0]) if pf else None  # ← hardcoded index 0
```

For Phase 4/5 topology, the `implementation → review` handoff has `propagate_fields=(CUSTOM_FIELD_INTERFACE_REF, CUSTOM_FIELD_TEST_SUITE_REF)`, so `pf[0]` happens to be `CUSTOM_FIELD_INTERFACE_REF`. But there's no semantic enforcement — the code relies on position 0 always being the interface ref.

## Impact

- If the order of `propagate_fields` is ever changed in a `StageHandoff` definition, the `LINK_TYPE_IMPLEMENTS` link could silently point to the wrong work item (e.g., a test_suite instead of an interface_spec).
- Adding a new `propagate_fields` entry in first position would silently break all `implements` link creation.
- No tests caught this because the test topology always matches the current ordering.

## Fix

The scheduler should name-lookup within `propagate_fields` rather than using index 0. Either match `pf` tuples against `CUSTOM_FIELD_INTERFACE_REF` explicitly, or make `propagate_fields` a `dict[str, str]` mapping field names to their propagation sources.
