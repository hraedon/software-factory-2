---
number: "155"
title: "Integrator and OutcomeVerifier excluded from inner gate retries in Phase 5"
severity: high
status: resolved
kind: bug
author: agent
date: "2026-05-15"
tags: [runner, pre_gate, stage-8, stage-9]
related: []
---

## Summary

`_INNER_GATE_ROLES` in `runner.py:69-74` is a frozen set that controls which roles get inner gate (pre-submission) retries. It includes `ROLE_INTERFACE_ARCHITECT`, `ROLE_TEST_AUTHOR`, and `ROLE_IMPLEMENTER`, but when `ROLE_INTEGRATOR` and `ROLE_OUTCOME_VERIFIER` were introduced in Phase 5, they were never added to this set.

```python
# runner.py:69-75
_INNER_GATE_ROLES = frozenset(
    {
        ROLE_INTERFACE_ARCHITECT,
        ROLE_TEST_AUTHOR,
        ROLE_IMPLEMENTER,
    }
)
```

This means `role_name in _INNER_GATE_ROLES` at line 458 is `False` for integrator and outcome_verifier, so even when `config.inner_gate_retries > 0`, those roles skip the inner gate loop entirely.

## Impact

- Integrator-produced `assembled_tree` artifacts skip import check, mypy, and pytest pre-submission validation.
- Outcome-verifier verdicts skip structural validation.
- If an integrator produces a malformed assembly with broken imports, the error is only caught at the outer gate (post-submission), costing a full submit-and-gate cycle.
- This is a silent omission — no warning is logged when a role is excluded from inner gate.

## Fix

Add `ROLE_INTEGRATOR` and `ROLE_OUTCOME_VERIFIER` to the `_INNER_GATE_ROLES` set, with appropriate inner gate implementations for each role.
