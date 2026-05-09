---
number: "069"
title: "Gate names are bare string literals scattered across gate.py — no constants or closed set"
severity: medium
status: resolved
kind: improvement
author: opencode
date: "2026-05-09"
tags: [gate, telemetry, runner]
related: ["056", "068"]
---

## Summary

Gate names like `"interface_spec_syntax"`, `"impl_mypy"`, `"impl_pytest"`, `"test_suite_dependency"`, `"implementation_dependency"` are bare string literals constructed at multiple `GateResult` sites in `gate.py` and consumed in `telemetry.py`. BC-056/065 centralized identifiers into `constants.py` to prevent "string constant gravity," but gate names were never given that treatment.

## Impact

- Typos in gate names (e.g. `"impl_mypy"` vs `"impl_myppy"`) would silently corrupt pass-rate tables — the type checker cannot catch them.
- No closed set of valid gate names exists, so the telemetry `unknown`-gate-name warning can't reference an enumeration of expected values.
- Adding a new gate requires finding all the string literal sites by grep rather than adding a constant.

## Proposed fix

Add a `GateName` enum or a set of `GATE_NAME_*` constants to `constants.py`, mirroring the existing pattern for transition names and work item types. Replace all bare string literals in `GateResult` construction sites. Optionally: add a `validate_gate_name()` helper that telemetry can call to detect both unknowns and typos against the closed set.