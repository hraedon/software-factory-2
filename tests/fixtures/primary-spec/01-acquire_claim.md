# acquire_claim — Pure Interface

## Source
substrate spec §5, FR-06

## Spec excerpt

**FR-06:** Acquire a claim on a work-item. Respects `not_before` (rejects if in future); rejects if work-item is already claimed and unexpired (Postgres row lock — first wins, second receives "claim contested" rejection, not an error). Auto-steal expired claims on next acquire; increment `attempt_number`; preserve prior claim history in event log.

**AC-06:** Given a work-item with `not_before` in the future, claim acquisition rejects. Given an unclaimed work-item, two concurrent acquires result in exactly one success and one "claim contested" rejection. Given an expired claim, auto-steal increments attempt_number.

## Work-item shape
pure-interface — single function with typed signature, no enumerated error return

## AC IDs
AC-06
