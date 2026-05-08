---
number: "045"
title: "report.py hardcodes workflow_version=1 — cannot report on Phase 2 runs"
severity: medium
status: resolved
kind: bug
author: adversarial-review
date: "2026-05-08"
tags: [telemetry, reporting]
related: ["033"]
---

## Problem

`report.py:18` hardcodes `workflow_version=1` in the `query_work_items` call:

```python
page = sub.query_work_items(
    workflow_name="software_factory",
    workflow_version=1,
    page_size=50,
)
```

All golden runs 002 and 003 used workflow version 2 (phase2.yaml). The report script cannot query or report on any Phase 2 run data. BC-033 already tracks the broader telemetry reporter skeleton; this is a specific bug in the existing reporting path that blocks even basic Phase 2 readout.

## Fix

1. Add `--workflow-version` argument to `report.py` (default to current version, or read from config).
2. Update the per-item detail loop to handle test_suite and implementation work_item_type custom_fields (they have different field names than interface_spec).
3. Add Phase 2-specific summary sections (per-stage pass rates, escalation paths).

## Resolution

Items 1 resolved: `report.py` now reads `workflow_name` and `workflow_version` from `FactoryConfig` instead of hardcoded values. Items 2-3 remain as improvements for Phase 2 maturation (BC-033 covers the broader telemetry reporter).
