---
number: "185"
title: "split GateResult.custom_fields into transition_fields and routing_fields"
severity: medium
kind: refactor
status: implemented
author: claude
date: "2026-05-17"
tags: [gate, gate-process, scheduler, routing, design, phase5]
related: ["180", "145"]
---

## Symptom

BC-180 fixed a CUSTOM_FIELD_VIOLATION crash-loop by adding a runtime filter
in `gate_process.py` that drops `GateResult.custom_fields` entries the current
work item type doesn't declare. The filter is defensive but papers over a
deeper design issue: `GateResult.custom_fields` is an untyped grab bag with
two distinct producers feeding two distinct consumers, and they were getting
crossed.

| Producer | Where | Intended consumer | Where |
|---|---|---|---|
| `evaluate_review()` (diagnostics for the review item) | `gate.py:1017` | the review work item's transition payload | `gate_process.py:367-368` (pre-BC-180) |
| `evaluate_review()` (data for the upstream revision) | `gate.py:1017` | `ensure_upstream_revision` → new implementation revision | `scheduler.py:302` |

Both producers used the same field (`review_findings`); only the second
consumer's target (`implementation`) declared the field, so the first
consumer's write blew up. Any future gate evaluator that adds a new field
to `custom_fields` faces the same trap: silently dropped (BC-180 filter) or
crashy (pre-BC-180) depending on which work item type is on the receiving end.

## Root cause

`GateResult.custom_fields: dict[str, Any]` carries fields with two
semantically different destinations through a single channel. The producer
cannot signal "this field belongs on the current transition" vs "this field
belongs on the upstream revision the router will create from this verdict."
Downstream consumers guess based on the work item type, which is the wrong
abstraction — the work item type is the *current* item, not the *target* item.

## Proposed fix (Option B from the BC-180 discussion)

Split `GateResult.custom_fields` into two explicit bags:

```python
@dataclass
class GateResult:
    ...
    transition_fields: dict[str, Any] = field(default_factory=dict)
    """Custom fields to merge into the current work item's transition payload."""

    routing_fields: dict[str, Any] = field(default_factory=dict)
    """Custom fields to propagate to an upstream revision created by the router."""
```

Migration:
- `evaluate_review` puts `review_findings` in `routing_fields` only.
  Diagnostic-style fields (e.g. summary text the review item should carry)
  go in `transition_fields`.
- `gate_process.py`'s transition-payload assembly reads only `transition_fields`.
  Delete `_wi_type_has_field` and its filter introduced by BC-180 — no longer
  needed, since the producer's intent is now explicit.
- `scheduler.ensure_upstream_revision` reads only `routing_fields`.
- Migrate any other gate evaluator that populates `custom_fields` today —
  audit `gate.py` for `GateResult(...custom_fields=...)` call sites.

For backwards compatibility during migration: temporarily keep
`custom_fields` as a deprecation alias that maps to `transition_fields` and
log a warning. Remove after one cycle.

## Acceptance criteria

- AC-1: `GateResult` has explicit `transition_fields` and `routing_fields`
  attributes; tests cover that each lands on the correct consumer.
- AC-2: `evaluate_review` routes `review_findings` to `routing_fields`;
  regression test verifies the field reaches the new implementation revision
  via `ensure_upstream_revision`.
- AC-3: `gate_process.py` no longer needs the BC-180 `_wi_type_has_field`
  filter for *destination correctness* (it may remain as a sanity check or
  be removed entirely — implementer's call).
- AC-4: No existing test regresses; regista accepts review transitions
  with `transition_fields` payloads.
- AC-5: One end-to-end test driving a review-found-defect path confirms
  `review_findings` is present on the new implementation revision and
  absent on the review work item's stored fields.

## Fix

### Audit: GateResult call sites that populate custom_fields

Only one call site in `gate.py` used `custom_fields`:

| Evaluator | Field | Old bag | New bag | Justification |
|---|---|---|---|---|
| `evaluate_review` | `review_findings` | `custom_fields` | `routing_fields` | Field is for the new implementation revision created by `ensure_upstream_revision`, not for the review work item's transition payload |

No other `GateResult(...)` call uses `custom_fields`. The deprecation alias is
available but unused in production code.

### Implementer's call on BC-180 filter

`_wi_type_has_field` and the filter loop in `gate_process.py` were **removed
entirely**. The producer's intent is now explicit: `transition_fields` goes to
the current work item's transition; `routing_fields` goes to upstream revisions.
A filter that introspects the workflow schema to compensate for ambiguous
producer intent is no longer necessary. The `TestWiTypeHasField` test class
(which directly tested that helper) was removed accordingly.

### Deprecation alias

`GateResult.custom_fields` is kept for one migration cycle. It maps to
`transition_fields` via `__post_init__` (frozen dataclass uses
`object.__setattr__`) and emits `DeprecationWarning`. No production code uses
it after this change.

### ensure_upstream_revision

Added `gate_result: GateResult | None = None` parameter. When
`gate_result.routing_fields` contains `review_findings`, it uses those
structured findings directly. Falls back to constructing from `route.diagnostics`
when no routing_fields are present (preserves backward compat for any call
site that passes `gate_result=None`).

## Touched surface (actual)

- `src/factory/gate.py` — `GateResult` dataclass: added `transition_fields`,
  `routing_fields`, `__post_init__` deprecation alias; migrated
  `evaluate_review` from `custom_fields` to `routing_fields`; added `import warnings`.
- `src/factory/gate_process.py` — removed `_wi_type_has_field`; updated
  `process_gate_item()` to read `transition_fields`; passes `gate_result` to
  `ensure_upstream_revision`.
- `src/factory/scheduler.py` — added `gate_result` parameter to
  `ensure_upstream_revision`; prefers `routing_fields` over `route.diagnostics`
  for `review_findings`; added `from factory.gate import GateResult`.
- `tests/test_bc145_routing.py` — updated `custom_fields` ref to
  `routing_fields`; removed deprecated `custom_fields=` from router dispatch test.
- `tests/test_upstream_routing.py` — added `TestBC185RoutingFields` class (4
  tests: AC-1, AC-2, fallback, separation).
- `tests/test_gate_process_budget_and_field_validation.py` — removed
  `TestWiTypeHasField` (8 tests); updated `TestReviewFindingsFilteredOnReviewType`
  assertion message; added `TestBC185ReviewFoundDefectE2E` (1 test, AC-5 e2e).

## Test results

994 passed, 13 skipped, 0 failures (full suite).

## Severity rationale

Medium. The latent bug class is real but BC-180's filter makes it safe in
practice. The refactor reduces a category of future bugs and makes the
review→implementation revision path self-documenting. Worth doing while
the BC-180/145 context is fresh.

## Out of scope

- Changing the workflow schema or regista's custom_field validation —
  this is purely an internal-API split in sf2's gate-result data model.
- Adding new fields beyond what producers emit today.
