---
number: "178"
title: "Tighten upstream_revision_of to target_work_item_types: [review, jury] by moving declaration to phase4"
severity: low
status: implemented
kind: improvement
author: gr035-followup
date: "2026-05-16"
tags: [workflow, composition, BC-145, BC-171]
related: ["145", "171"]
---

## Context

After substrate BC-171 landed (plural `target_work_item_types`), sf2 could
tighten `upstream_revision_of` from a no-target `work_item_ref` to
`target_work_item_types: [review, jury]` — recovering the bounded-target
validation the original GR-035 `string` workaround had abandoned.

The naive change (add `target_work_item_types: [review, jury]` to the field
in `phase2.yaml`) fails registration because `phase2.yaml` does not declare
`review` or `jury` work_item_types. Those are added in `phase4.yaml`. Any
test (e.g. `test_phase2_workflow_roundtrip`) that registers phase2
standalone breaks with `WORKFLOW_SEMANTIC_ERROR: references unknown
work_item_types: ['jury', 'review']`.

## Path forward

Substrate's `_workflow_compose._deep_merge` does support adding fields to
an inherited work_item_type via `custom_fields__append:`. The clean shape
is:

1. In `workflows/phase2.yaml`: remove `upstream_revision_of` (and
   `review_findings`) from `implementation.custom_fields`. Phase 2
   standalone has no upstream routing, so the field is unused at that
   tier.
2. In `workflows/phase4.yaml`: under `work_item_types: - name:
   implementation`, add:
   ```yaml
   custom_fields__append:
     - name: upstream_revision_of
       type: work_item_ref
       target_work_item_types: [review, jury]
       required: false
       ui_visible: true
     - name: review_findings
       type: json
       required: false
       ui_visible: false
   ```
3. Audit `src/factory/scheduler.py:ensure_upstream_revision` and
   `src/factory/constants.py` for any phase-2-standalone callsite that
   reads/writes these fields. If they're never written below phase 4
   (which is the design intent — only review/jury failures trigger them),
   no code change is needed.
4. Audit tests that load `phase2.yaml` standalone — ensure none of them
   set `upstream_revision_of` or `review_findings`. Update
   `test_upstream_routing.py` if it relies on the field being declared in
   phase2.

## Why deferred

Risk is non-trivial:
- `test_phase2_workflow_roundtrip` and other phase-2-loaded tests need
  inspection for accidental dependencies.
- `review_findings` is set on the same path as `upstream_revision_of`
  (`scheduler.py:274`), so both should migrate together.
- Worth bundling with the next workflow-composition cleanup pass rather
  than as a standalone change.

The benefit is small (validation tightening on a path already partially
constrained) and the no-target form preserves UUID + existence validation
in the meantime.

## Acceptance criteria

- AC-1: `phase4.yaml` (and through composition, `phase5.yaml` /
  `full_pipeline.yaml`) constrains `upstream_revision_of` to `[review,
  jury]`.
- AC-2: `phase2.yaml` no longer declares `upstream_revision_of` or
  `review_findings`.
- AC-3: Full test suite passes including
  `test_phase2_workflow_roundtrip`.
- AC-4: GR-036 (or successor) exercises the upstream routing path with
  the tightened constraint and observes correct rejection on a mismatched
  source type.

## Touched surface

- `workflows/phase2.yaml`, `workflows/phase4.yaml`.
- Possibly `tests/test_upstream_routing.py` if a test asserts the field
  exists at phase 2.

## Related

- BC-145 — original upstream-routing class of bugs.
- BC-171 (substrate, resolved) — provides the `target_work_item_types`
  feature this BC consumes.

## Resolution

Moved `upstream_revision_of` (with `target_work_item_types: [review, jury]`) and `review_findings` from `phase2.yaml` to `phase4.yaml` via `custom_fields__append` on the inherited `implementation` work_item_type. Phase 2 standalone no longer declares these fields. No phase2-standalone tests referenced them. 1008 tests pass.
