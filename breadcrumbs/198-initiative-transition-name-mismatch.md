---
number: "198"
title: "initiative.py requeue uses state name as transition name — no valid transition from cannot_proceed"
severity: high
status: proposed
kind: bug
author: self-audit
date: "2026-05-22"
tags: [runner, gate]
related: ["194"]
---

## Problem

`requeue_initiative()` at `initiative.py:117` calls `sub.transition(wi.work_item_id, "new", ...)`. This is intended to move a `cannot_proceed` item back to `new` state. However:

1. `"new"` is a **state name**, not a **transition name**. Regista's `transition()` takes a transition name that must be defined in the workflow YAML.
2. No workflow YAML defines a transition from `cannot_proceed` state. There is no `from: cannot_proceed` in any workflow file.

This would raise a `SubstrateError(NO_SUCH_TRANSITION)` at runtime.

Similarly, `cancel_initiative()` at line 82 uses `"cannot_proceed"` as a transition name, which happens to match a valid transition (from `in_progress` to `cannot_proceed`), but only if the item is in `in_progress` state. The filter on line 70 excludes `locked` and `cannot_proceed` items but not `new` or `gating` items, where the `cannot_proceed` transition may not be defined.

## Fix

1. Add a `"requeue"` transition to the workflow YAMLs: `from: cannot_proceed, to: new`
2. Use `TRANSITION_*` constants from `constants.py` instead of bare state names
3. Verify the item's current state allows the transition before calling `transition()`

### Why this isn't the previous fix recurring

The invariant missing in BC-194 was "long-running claims must heartbeat to prevent theft." BC-198 addresses a different invariant: "state machine transitions must use valid transition names, not state names." The two bugs are in different code paths (claim management in runner vs initiative API in initiative.py) and the BC-194 fix (HeartbeatSession) does not affect BC-198's failure mode at all. This is a distinct defect discovered during the same audit session, not a recurrence of the claim-theft issue.
