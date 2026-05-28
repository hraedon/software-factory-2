# create_link — Pure Interface

## Source
regista spec §5, FR-22

## Spec excerpt

**FR-22:** Create a link between work-items — validates target exists in same project DB, validates link type is allowed by workflow def for the work-item-type pair, records `link_created` event with `(from, to, type)`. Target in terminal state still allowed.

Link types are typed directed references between work-items in the same project. Created and removed via events. Cross-project links are not supported (BR-04).

**AC-22:** Link create with cross-project target rejects. Link create with disallowed type for the work-item-type pair rejects. Valid link creates and emits `link_created`. Target in terminal state still allowed.

## Work-item shape
pure-interface — single function with typed signature, no enumerated error return

## AC IDs
AC-22
