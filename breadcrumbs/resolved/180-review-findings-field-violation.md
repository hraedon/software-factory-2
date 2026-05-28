---
number: "180"
title: "gate_process writes review_findings to review work item type, causing CUSTOM_FIELD_VIOLATION crash-loop"
severity: critical
status: implemented
kind: bug
author: opencode
date: "2026-05-17"
tags: [gate, BC-145, review, custom-fields, phase5]
related: ["145", "179"]
---

## Symptom

When a review work item fails the cross-family review gate, `gate_process.py`
writes `review_findings` into the `custom_fields` payload of the `sub.transition()`
call. The `review` work item type does not declare `review_findings` in its
custom_fields schema — only `implementation` does. Regista rejects the
transition with `[CUSTOM_FIELD_VIOLATION] Unknown field 'review_findings'`,
the gate process catches the exception, releases the claim, and reclaims the
same item on the next polling cycle. This creates an infinite crash-loop
that ran for ~2h13m on two review items in GR-036 (reaching attempts 1676
and 1579).

## Root cause

`evaluate_cross_family_review()` in `gate.py` returns `GateResult.custom_fields`
containing `review_findings` when structured findings are parsed from the review
artifact. This field is intended for `ensure_upstream_revision` to propagate to
the new implementation revision. However, `process_gate_item()` line 367-368
unconditionally merges ALL `GateResult.custom_fields` into the transition
payload:

```python
custom_fields_payload: dict = {"diagnostics": diagnostics}
if gate_result.custom_fields:
    custom_fields_payload.update(gate_result.custom_fields)
```

When the work item being transitioned is a `review` type, `review_findings`
is not a valid field, and regista rejects the entire transition.

This is the **fifth** bug in the BC-145 family (review/jury verdict routing).
Predecessors: missing `test_suite_ref` propagation, missing workflow field
declarations, `upstream_revision_of` type mismatch (string vs work_item_ref),
and missing `interface_ref`/`test_suite_ref` on jury source.

## Fix

Added `_wi_type_has_field()` to `gate_process.py` that queries the workflow
definition to check whether a field is valid for the current work item type.
The custom_fields merge now iterates over `gate_result.custom_fields` and only
includes fields that are declared for the work item type, logging a warning
for skipped fields.

```python
if gate_result.custom_fields:
    for cf_key, cf_value in gate_result.custom_fields.items():
        if cf_key == "diagnostics":
            continue
        if _wi_type_has_field(sub, config, wi.work_item_type, cf_key):
            custom_fields_payload[cf_key] = cf_value
        else:
            log.warning("gate_skip_invalid_field", ...)
```

## Acceptance criteria

- AC-1: `TestReviewFindingsFilteredOnReviewType::test_review_findings_not_written_to_review_wi`
  verifies that `review_findings` is NOT written to a review work item, but
  `diagnostics` IS written.
- AC-2: `TestWiTypeHasField` (8 tests) verifies field presence/absence across
  all phase5 work item types.
- AC-3: GR-037 (or successor) exercises review-found-defect routing without
  crash-looping.
- AC-4: No regression in existing gate_process tests.

## Touched surface

- `src/factory/gate_process.py` — added `_wi_type_has_field()`, filtered
  custom_fields in `process_gate_item()`.
- `tests/test_gate_process_budget_and_field_validation.py` — new test file
  (11 tests: 8 field validation, 1 integration, 2 budget guardrail).

## Severity rationale

Critical. Two review items cycled 1600+ times each, consuming gate-process
CPU indefinitely with no budget check. The pipeline appeared to hang for the
user. Same blast radius as the original BC-145 bugs.