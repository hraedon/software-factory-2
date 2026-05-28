# Adversarial Item: Ambiguous Result Handling

## Source
Hand-authored (not from regista spec — intentionally ambiguous)

## Spec excerpt

**Feature:** `sort_records` function

Given a list of financial records (each with a `date`, `amount`, and `category`), `sort_records` should sort them and return reasonable results. The function should handle edge cases sensibly. It should work for most typical inputs that a line-of-business user would provide.

**Acceptance Criteria:**
- TS-ADV-01: The function accepts a list of records and returns sorted output.
- TS-ADV-02: The function handles edge cases reasonably.

## Work-item shape
adversarial — intentionally ambiguous AC designed to trigger `cannot_proceed`. Expected result: `{"status": "cannot_proceed", "reason": "Spec is ambiguous regarding sort order and edge-case handling", "gaps": [...]}`

## AC IDs
TS-ADV-01, TS-ADV-02
