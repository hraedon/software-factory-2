---
number: "158"
title: "Outcome-verifier routing_hint extracted in gate but never consumed by scheduler or runner"
severity: high
status: resolved
kind: bug
author: agent
date: "2026-05-15"
tags: [gate, scheduler, stage-9, failure-routing]
related: ["145", "160"]
---

## Summary

`evaluate_outcome_verification()` in `gate.py:1274-1282` extracts a `routing_hint` dict from the outcome-verifier verdict JSON when `verdict != "pass"`. This `routing_hint` is stored in `GateResult.routing_hint` and propagated through `gate_process.py` into telemetry diagnostics. But no code **reads** the `routing_hint` to actually route the result upstream.

```python
# gate.py:1274-1282
routing_hint: dict | None = None
if not passed:
    diagnostics.append(f"Outcome verification failed: {rationale or 'no rationale provided'}")
    vote_hint = vote.get("routing_hint")
    if isinstance(vote_hint, dict):
        hint_type = vote_hint.get("work_item_type", "unknown")
        hint_reason = vote_hint.get("reason", "")
        diagnostics.append(f"Routing hint: {hint_type} — {hint_reason}")
        routing_hint = vote_hint
```

The `routing_hint` is:
1. Stored in `GateResult.routing_hint` (a new optional field added in Session 36).
2. Injected into gate diagnostics by `gate_process.py` on outcome-verification failure.
3. Collected by `telemetry.py` (via `RoutingHintMetrics/collect_routing_hints`).

But the `Route` object for `DiagnosticKind.OUTCOME_E2E` routes to `STATE_NEW` (retry outcome verification), which is wrong — the outcome verifier has already determined the assembly doesn't meet requirements. The `routing_hint` suggests *where* to route (e.g., to the integrator or interface architect), but `STATE_NEW` just re-runs the same outcome-verifier role.

This is the same structural gap as BC-145 (review/jury routing) — the routing_hint signal exists but the routing infrastructure can't consume it.

## Impact

- Outcome-verification failures always retry the same role, wasting model budget on a role that already provided a definitive verdict.
- The `routing_hint` from the outcome verifier (which identifies the root cause stage) is displayed in telemetry but ignored by the scheduler/router.
- Without proper routing, the pipeline cannot recover from outcome-verification failures.

## Fix

The `OUTCOME_E2E` route in `_PHASE2_DISPATCH` (router.py:182-184) should route based on the `routing_hint` content:
- If `routing_hint.work_item_type == "interface_spec"` → route to interface architect.
- If `routing_hint.work_item_type == "implementation"` → route to implementer via new work item.
- Fallback → `cannot_proceed` (terminal).

## Resolution

OUTCOME_E2E with routing_hint now routes directly to STATE_CANNOT_PROCEED instead of STATE_NEW, preventing budget waste on re-running the outcome verifier. Full upstream routing (creating new work items for implementer/interface_architect) deferred to RFC-025.
