# Curated Test Set — Primary (from substrate spec)

Source: `/projects/substrate/spec.md`
Purpose: Phase 1 exit-criterion validation for SF2's `interface_architect` role.

This directory contains a partitioned spec for the 10-item primary test set.
Each section corresponds to one `interface_spec` work-item with explicit AC
references and work-item shape classification.

## Work-item partition

| Item | Shape | Substrate Function | ACs |
|------|-------|--------------------|-----|
| 01 | pure-interface | `acquire_claim` | AC-06 |
| 02 | pure-interface | `register_workflow` | AC-17 |
| 03 | pure-interface | `create_link` | AC-22 |
| 04 | error-taxonomy | `verify_event` (ErrorCode enum) | AC-15, AC-26 |
| 05 | error-taxonomy | `acquire_claim` errors (CLAIM_CONTESTED, NOT_BEFORE_FUTURE) | AC-06 |
| 06 | error-taxonomy | `transition` errors (INVALID_TRANSITION, ROLE_NOT_PERMITTED) | AC-11, AC-12 |
| 07 | ADT-validation | `DriftReport` (replay output) | AC-16 |
| 08 | ADT-validation | `create_work_item` with custom_fields schema | AC-02 |
| 09 | ADT-validation | `query_work_items` filter + QueryPage return type | AC-05b |
| 10 | ADT-validation | `DeadLetterEntry` + requeue API | AC-14 |

Three shape categories, at least 3 items each. Per `plans/phase1-implementation.md`
Wave 6 exit criteria: ≥9/10 first-attempt pass with ≥2/3 in each category.

## Sections below

Each section is a self-contained spec excerpt that the `interface_architect`
role receives as `spec_section`. AC IDs reference acceptance criteria from the
substrate spec where they exist; for new ACs specific to this test set, they
use the format `TS-NN`.