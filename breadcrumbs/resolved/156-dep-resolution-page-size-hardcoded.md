---
number: "156"
title: "_find_locked_impl uses hardcoded page_size=200 instead of config value"
severity: medium
status: resolved
kind: bug
author: agent
date: "2026-05-15"
tags: [scheduler, dep_resolution, config-drift]
related: []
---

## Summary

`_find_locked_impl()` in `dep_resolution.py:101-104` hardcodes `page_size=200` when querying for locked implementations, instead of using `config.query_page_size`. If a project has more than 200 locked implementations, the query silently truncates results and may fail to find a matching implementation.

```python
# dep_resolution.py:101-104
impls = substrate.query_work_items(
    work_item_types=[WORK_ITEM_TYPE_IMPLEMENTATION],
    current_states=[STATE_LOCKED],
    page_size=200,  # ← should be config.query_page_size
)
```

## Impact

- For large multi-module projects with 200+ locked implementations, dependency resolution silently returns no match for some dependencies, causing spurious "cannot_proceed" escalations.
- The bug is latent — it only manifests on projects large enough to trigger the pagination boundary.

## Fix

Replace `page_size=200` with a mechanism to accept the config value. Since `_find_locked_impl` is a module-level function without direct config access, either thread a `page_size` parameter through or make it a method on a config-aware object.
