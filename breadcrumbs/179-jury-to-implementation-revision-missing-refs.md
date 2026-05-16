---
number: "179"
title: "ensure_upstream_revision builds invalid implementation payload when source is jury (missing interface_ref/test_suite_ref)"
severity: high
status: proposed
kind: bug
author: bc145-coverage-followup
date: "2026-05-16"
tags: [scheduler, upstream-routing, BC-145, jury, phase4]
related: ["145", "171"]
---

## Symptom

When a `jury` work item fails and routes to an implementation revision via
`ensure_upstream_revision`, substrate rejects the `create_work_item` call
with:

```
SubstrateError: [CUSTOM_FIELD_VIOLATION] Required field 'interface_ref'
  missing
```

(and similarly for `test_suite_ref`). The new integration test in
`tests/test_upstream_routing_integration.py::test_jury_to_implementation_revision_passes_substrate_validation`
xfails on this exact path.

## Why GR-035 didn't surface it

GR-035 reached the jury stage successfully (2/2 jury items locked), so no
jury ever failed; the jury→implementation routing branch was dead-code
during the run. The three bugs that GR-035 *did* surface were all on the
review→implementation path. The jury path is structurally identical but
broken by a different schema mismatch.

## Root cause

`ensure_upstream_revision` (`src/factory/scheduler.py:264-270`) copies
`interface_ref` and `test_suite_ref` from `source_wi.custom_fields`. This
works for `review` sources because `phase4.yaml` declares both fields on
the `review` work_item_type. It fails for `jury` sources because
`phase4.yaml`'s `jury` declares only:

- `review_ref` (work_item_ref → review, required)
- `spec_section`, `ac_ids` (required)
- a small handful of jury-specific fields

`interface_ref` and `test_suite_ref` are not in jury's schema, so
`source_custom.get(CUSTOM_FIELD_INTERFACE_REF)` returns `None`, the field
is omitted from the payload, and substrate rejects the
`create_work_item` because `implementation` requires both refs.

## Fix direction

The information *does* exist, just one hop away: jury → `review_ref` →
review → `interface_ref`/`test_suite_ref`. `ensure_upstream_revision`
needs to resolve through the link when the source is a jury:

```python
interface_ref = source_custom.get(CUSTOM_FIELD_INTERFACE_REF)
test_suite_ref = source_custom.get(CUSTOM_FIELD_TEST_SUITE_REF)
if (not interface_ref or not test_suite_ref) and source_wi.work_item_type == WORK_ITEM_TYPE_JURY:
    review_ref = source_custom.get(CUSTOM_FIELD_REVIEW_REF)
    if review_ref:
        review_wi = sub.get_work_item(uuid.UUID(review_ref))
        review_custom = review_wi.custom_fields or {}
        interface_ref = interface_ref or review_custom.get(CUSTOM_FIELD_INTERFACE_REF)
        test_suite_ref = test_suite_ref or review_custom.get(CUSTOM_FIELD_TEST_SUITE_REF)
```

(Pseudocode — the constants already exist in `factory.constants`; the
work_item_type check should use the existing `WORK_ITEM_TYPE_JURY`.)

An alternative would be to add `interface_ref`/`test_suite_ref` to the
`jury` work_item_type schema and propagate them from review at jury
creation. That changes the data model but keeps the scheduler simple.
The first option is less invasive and matches how the rest of the
routing code resolves refs through links.

## Acceptance criteria

- AC-1: `test_jury_to_implementation_revision_passes_substrate_validation`
  passes (remove the `xfail` decorator).
- AC-2: No regression in
  `test_review_to_implementation_revision_passes_substrate_validation` or
  in `tests/test_upstream_routing.py` mocked unit tests.
- AC-3: A new mocked unit test in `test_upstream_routing.py` confirms the
  link-resolution code path is exercised when the source is a jury.
- AC-4: GR-036 (or successor) exercises a jury-failure routing scenario
  without erroring out of the gate.

## Touched surface

- `src/factory/scheduler.py:ensure_upstream_revision`.
- `tests/test_upstream_routing.py` — add mocked unit test for the
  link-resolution path.
- `tests/test_upstream_routing_integration.py` — remove `xfail` from the
  jury test.

## Severity rationale

High. This is a silent dead-letter on a routing path that *will*
trigger in real golden runs as soon as any jury fails. The first time
jury feedback escalation actually fires, the gate process will
crash-loop similar to the GR-035 attempts 3-4 cycling — until the bug is
fixed. Same blast radius as the original three BC-145 bugs.

## Related

- BC-145 — sibling routing bugs; this is the fourth in the family.
- BC-171 — substrate plural target support; orthogonal but tightening to
  `target_work_item_types: [review, jury]` would have surfaced this bug
  faster (via type-rejection) had the constraint been live.
