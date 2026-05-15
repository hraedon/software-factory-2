---
number: "151"
title: "Integration success reports wrong gate name — telemetry counts pass as integration_import event"
severity: high
status: resolved
kind: bug
author: agent
date: "2026-05-15"
tags: [gate, telemetry, stage-8]
related: []
---

## Summary

`evaluate_integration()` in `gate.py:1247-1251` returns `gate_name=GATE_NAME_INTEGRATION_IMPORT` on success, even when all three gates (import, mypy, pytest) passed. This means a successful integration evaluation is telemetrically indistinguishable from an import-gate pass event, skewing per-gate pass rates.

```python
# gate.py:1247-1251
return GateResult(
    passed=True,
    gate_name=GATE_NAME_INTEGRATION_IMPORT,  # ← should be a generic success name
    diagnostics=[],
)
```

## Impact

- Telemetry reports integration pass events under the `integration_import` gate name, inflating its pass rate.
- The mypy and pytest integration gates never see a success event in telemetry — only failures.
- When debugging pipeline behavior, it's impossible to distinguish "import check passed" from "entire integration passed."

## Fix

Add a `GATE_NAME_INTEGRATION` constant (or use `""` to mean "passed all sub-gates") and return it on success.
