---
number: "080"
title: "Router target_role is dead output — architecture suggests capability that doesn't exist, ignored by every consumer"
severity: medium
status: resolved
kind: bug
author: deepseek-v4-pro (adversarial review — Session 20)
date: "2026-05-11"
tags: [router, failure-routing, runner, gate]
related: ["055", "027"]
---

## Problem

`router.py:79-164` (`_PHASE2_DISPATCH`) assigns a `target_role` to every `DiagnosticKind`. For example:
- `DiagnosticKind.TEST_COLLECT` → `target_role=ROLE_TEST_AUTHOR`
- `DiagnosticKind.CANNOT_PROCEED_SEAM` → `target_role=ROLE_INTERFACE_ARCHITECT`

But `runner.py:worker_loop()` determines the invoking role via `_role_for_type(wi.work_item_type, config)`, which maps by work item type using `config.type_to_role`. The router's `target_role` is **never read by any consumer**. GR002 Finding 2 discovered this indirectly: escalation diagnostics with `target_role="interface_architect"` were produced but the worker continued to dispatch implementation items to the `implementer` role regardless.

## Impact (current)

For Phase 2 (1:1 type→role mapping), this is functionally harmless. The work-item type is always a reliable signal for role dispatch, and `target_role` happens to match in the common case.

## Impact (future)

For Phase 4+ (jury, race, cross-family review), the router's `target_role` encodes architectural intent that is structurally ignored. If a future phase introduces work items that should route to a different role based on diagnostic content (not just item type), the router has the data but the runner ignores it. This would surface as a routing bug that the code appears to handle but silently doesn't.

## Proposed fix

Either:
1. **Remove `target_role` from `Route`** — acknowledge that role dispatch is type-driven, not diagnostic-driven, and stop encoding intent that can't be acted on. This is the honest option for Phase 2. If a future phase genuinely needs diagnostic→role routing, the field can be re-added with a consumer that uses it.
2. **Wire `target_role` into the worker loop** — change `_role_for_type()` to prefer router-assigned roles over type-derived roles when available. Higher design risk; requires validating that role remapping doesn't break claim lifecycle.
3. **Document as advisory-only** — add a comment in `router.py` that `target_role` is informational for audit/telemetry and not used for dispatch. Not recommended; it's too easy to assume otherwise when reading the code.

Option 1 is recommended for Phase 2.

## Resolution

Applied Option 1: removed `target_role` field from `Route` dataclass, all `_PHASE2_DISPATCH` entries, `route()` function, and `custom_fields_update` diagnostics dict. Role dispatch is type-driven via `_role_for_type()` in runner.py. If Phase 4+ needs diagnostic-driven role routing, the field can be re-added with an actual consumer. Added introspection test verifying Route has no `target_role` field.
