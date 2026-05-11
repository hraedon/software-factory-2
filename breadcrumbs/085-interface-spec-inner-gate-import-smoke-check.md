---
number: "085"
title: "Interface spec inner gate — import smoke check before outer submission"
severity: medium
status: implemented
kind: improvement
author: opus-4.7
date: "2026-05-11"
tags: [runner, gate, stage-3, pre-gate]
related: ["075", "086"]
---

## Problem

The interface_spec gate can lock an artifact that contains invalid Python (e.g., `@dataclass(frozen=True)` misuse, syntax that mypy accepts in stub form but breaks at runtime import). Downstream test_suite items then fail at `pytest --collect-only` with `ImportError`, escalating to `cannot_proceed` after the attempt threshold.

GR-014 example: fr04_alerts test_suite escalated because the locked interface artifact's `AlertConfig` dataclass could not be imported. The interface_spec stage had already locked, so the failure surfaced one stage downstream — too late for a cheap retry, and against an item (test_suite) that is not actually broken.

This is the same class of issue BC-075 addressed at the implementation stage: give the producing role fast feedback on its own output before it is locked.

## Proposed resolution

Extend `pre_gate.py` with `pre_gate_interface_spec()` that runs, in short-circuit order:

1. Existing mechanical checks (mypy on the `.pyi` if any, structural validation).
2. **New:** `python -c "import <module>"` against the produced `.py` artifact in a clean tempdir with dep `.pyi` stubs on the path. Captures `ImportError`, `SyntaxError`, `TypeError` from decorator/metaclass evaluation.

On failure, the interface_architect retries with the diagnostic in `prior_failures`, identical to the BC-075 implementer flow. Inner gate retries bounded by `inner_gate_retries` (currently 2).

## Why this is high-leverage

Interface_spec failures fan out: one bad interface blocks one test_suite *and* one implementation (and any downstream modules depending on it). Catching the failure at the producing stage converts a fan-out `cannot_proceed` into a single cheap retry. Estimated to recover ~half of the residual GR-014 tail.

## Out of scope

- Static analysis beyond import (covered by existing mypy gate).
- Behavioral validation of the interface (no fixtures or test cases at this stage).
- Cross-module import checks — the interface_spec stage doesn't yet have locked deps; that remains the test_suite/implementation gate's responsibility.

## Validation plan

Re-run GR-014 fixture after landing. Expected: fr04_alerts (or equivalent invalid-dataclass failures) caught at interface_spec inner gate, retried, and locked correctly. Overall lock rate target: ≥95%.
