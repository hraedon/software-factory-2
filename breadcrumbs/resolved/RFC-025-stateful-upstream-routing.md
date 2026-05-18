---
number: "RFC-025"
title: "Stateful upstream routing — route() and scheduler need role-targeted work-item creation, not STATE_NEW retry"
severity: high
status: implemented
kind: design
author: agent
date: "2026-05-15"
tags: [rfc, failure-routing, router, scheduler, stage-5, stage-6, stage-7]
related: ["145", "158"]
---

## Summary

The current routing architecture has a fundamental design limitation: `route()` (router.py) can only dispatch to `STATE_NEW` (retry same work item) or `STATE_CANNOT_PROCEED` (terminal). It cannot:

1. **Route to a different role** — send a review failure to the implementer (upstream), not retry the reviewer.
2. **Route to a different work item** — create a new implementation work item with review feedback, rather than retrying the same review.
3. **Route with state** — carry the routing_hint or review findings through to the new work item's context.

This is the root cause of BC-145 (review/jury failure routing) and BC-158 (outcome-verifier routing_hint never consumed). The router was designed for a 3-stage pipeline (interface → test → implement) where every failure naturally routes back to the same work item. Phase 4 (review + jury) and Phase 5 (integration + outcome verification) introduced cross-role routing requirements that the router cannot satisfy.

## The design gap

**Current architecture:**
```
route(gate_fail) → STATE_NEW → work item re-claimed by same role
```

**What Phase 5+ needs:**
```
route(gate_fail with diagnostic_kind=review_found_defect) 
  → create new implementation work item 
  → carry review findings as context
  → bind to implementer role
```

The router is a pure function that maps `(state, transition, gate_result) → Route(target_state, custom_fields_update)`. It has no awareness of:
- Which work item produced the gate event
- Which upstream work items exist
- What role should handle the next attempt
- What context (review findings, routing_hint) carries over

The scheduler has work-item creation logic (`_ensure_downstream_item`) but only operates on the `stage_topology` — it creates one downstream item per handoff per source item. It has no concept of "create a new upstream revision in response to a gate failure."

## Design sketch for stateful routing

One approach: extend the route result to include a `new_work_item` directive:

```python
@dataclass(frozen=True)
class Route:
    target_state: str
    custom_fields_update: dict | None = None
    create_upstream_revision: bool = False  # NEW
    upstream_type: str | None = None        # NEW — e.g., "implementation"
    context_from: str | None = None         # NEW — e.g., "review_feedback"
```

The scheduler or gate_process would then:
1. Read the route result.
2. If `create_upstream_revision=True`, create a new work item of `upstream_type` with the context carried forward.
3. Set `review_feedback_pending=True` or equivalent on the new item's custom_fields.

This decouples routing logic (router knows where to go) from work-item creation (scheduler knows how to create).

## Constraints

1. Must not create duplicate upstream revisions — a work item that already has a pending upstream revision should not get another one.
2. Must preserve attempt budget — the new upstream item should inherit the attempt number or have its own counter.
3. Must handle supersession — if a new implementation locks, all downstream items (test_suite, review, jury, integration) for the old implementation should be superseded.

These constraints overlap with RFC-021 (spec mutation/invalidation policy) and BC-120 (implementer-initiated interface amendment). A unified stateful routing design should address all three.

## Phase needed

Phase 5–6. BC-145 is Phase 5 scope, but the routing infrastructure change is large enough to warrant design review before implementation.
