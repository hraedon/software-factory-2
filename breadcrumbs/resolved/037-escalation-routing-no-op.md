---
number: "037"
title: Escalation routing is a no-op for non-interface_spec work item types
severity: high
status: resolved
kind: bug
author: opencode
date: "2026-05-08"
tags: [runner, gate, failure-routing, stage-4, stage-5]
related: ["027"]
resolution: "Added gate_escalation transition (gating → cannot_proceed) to workflow YAMLs; router returns target_state=cannot_proceed on escalation; gate_process.py uses gate_escalation transition instead of gate_fail when escalation fires. Items now terminate in cannot_proceed instead of cycling indefinitely."
---

## Problem

When the router's escalation logic triggers for implementation or test_suite work items (same diagnostic kind exceeds `attempt_threshold`), it produces a `cannot_proceed_seam` route with `target_role="interface_architect"`. But the item goes back to state `new`, and the worker determines the processing role from `config.type_to_role` (implementation → implementer), ignoring the diagnostic's `target_role`. The implementer re-claims the item, produces another failing artifact, and the cycle repeats indefinitely.

## Evidence

Golden run 002: implementation items with `cannot_proceed_seam` diagnostics continued cycling for up to 80 additional attempts after escalation fired. Total waste: ~203 Claude CC invocations on implementations that could never pass.

```
053f9399  escalated_after_attempts=80  (still cycling)
0d936cfc  escalated_after_attempts=26  (still cycling)
128a05c4  escalated_after_attempts=30  (still cycling)
```

## Root Cause

`router.route()` at line 180-199 produces escalation diagnostics but returns `Route(target_state="new")`. The `target_role` field is advisory — `gate_process.py` never reads it to change the work item's type or transition it to a terminal state. The worker's claim filter in `runner.py` matches on `type_to_role`, which always maps `implementation → implementer`.

## Proposed Fix (Option A — simplest for Phase 2)

When escalation fires for a non-interface_spec work item, transition the item to `cannot_proceed` (terminal state) instead of back to `new`. This stops the retry loop and surfaces the failure to the principal via regista's dead-letter mechanism. The escalation diagnostics (including the original gate failure messages and attempt count) are preserved on the work item's `diagnostics` custom field.

Phase 3+ can implement option B (create a new interface_spec work item with escalation context) when the principal wants automated contract revision instead of manual surfacing.

## Location

- `src/factory/router.py:180-199` — escalation route produces `target_state="new"`
- `src/factory/gate_process.py:146-177` — gate applies route but doesn't transition to terminal on escalation
