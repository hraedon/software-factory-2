---
number: "086"
title: "Test suite inner gate — pytest --collect-only before outer submission"
severity: medium
status: implemented
kind: improvement
author: opus-4.7
date: "2026-05-11"
tags: [runner, gate, stage-4, pre-gate]
related: ["075", "085"]
---

## Problem

The test_suite role can produce an artifact whose own imports fail — a self-inflicted `ImportError` against `artifact.py`, a typo'd symbol from the interface, etc. Today this is caught only at the outer `test_suite_collect` gate, which costs a full claim/submit/gate cycle per retry and burns toward `attempt_threshold` quickly.

GR-014 example: fr01_dashboard test_suite escalated because the model-generated test code could not import its own artifact. Inner-loop feedback would have let the model see the diagnostic and self-correct within the same claim window.

This mirrors BC-075's implementer inner loop and is symmetric with BC-085's interface_spec inner loop.

## Proposed resolution

Add `pre_gate_test_suite()` to `pre_gate.py` running, in short-circuit order:

1. Existing mechanical checks (ruff, mypy on the test artifact).
2. **New:** `pytest --collect-only` against the test_suite artifact in the gate-style tempdir with dependency `.pyi` stubs and the locked interface `.py` on the path. Captures `ImportError`, `CollectError`, and unresolved fixtures.

Failure routes through `_inner_gate_loop()` with `gate_name=inner_test_collect` and the truncated pytest diagnostic in `prior_failures`. Bounded by `inner_gate_retries`.

## Why this is high-leverage

Collection failures are mechanical and self-evident from the diagnostic — exactly the failure class where one extra round of feedback is reliably effective. They also block the implementation stage entirely (no test → no impl), so each recovered test_suite recovers an implementation slot too.

## Out of scope

- Running the tests themselves (test_suite is a TDD artifact — tests *should* fail until the implementation lands; only collection should pass).
- Behavioral coverage analysis (existing outer gate's job).

## Validation plan

Re-run GR-014 fixture after landing alongside BC-085. Expected: fr01_dashboard-style import failures caught at inner gate, retried, and locked. Combined with BC-085, overall lock rate target ≥95% and `cannot_proceed` reserved for genuine model exhaustion.
