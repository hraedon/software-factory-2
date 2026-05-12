---
number: "129"
title: "Substrate actor_metadata API change breaks 10 integration tests — dict vs attribute access"
severity: high
status: proposed
kind: bug
author: glm-5.1
date: "2026-05-12"
tags: [substrate, test, dep-substrate, phase-3]
related: []
---

## Problem

10 tests fail against current substrate with `AttributeError: 'dict' object has no attribute 'value'` in `substrate/_events.py:226`. The substrate API appears to have changed `actor_metadata` from an object with `.value` attribute to a plain dict, but the factory tests still pass dicts to substrate APIs that expect the old shape.

Failing tests:
- `test_gate_process.py::TestGateProcessIntegration::test_gate_passes_valid_artifact`
- `test_phase2_workflow_roundtrip.py` (7 tests)
- `test_pipeline_integration_real.py::TestPipelineIntegrationReal::test_interface_spec_lifecycle_on_real_substrate`
- `test_runner_smoke.py` (2 tests)

## Reproduction

```bash
.venv/bin/python -m pytest tests/test_gate_process.py::TestGateProcessIntegration::test_gate_passes_valid_artifact -v
```

## Notes

- Pre-existing — confirmed these failures exist on unmodified HEAD (`dbebac7`).
- Not introduced by RFC-015 or BC-126/127/128 changes.
- Blocks CI from passing cleanly on `make check`. Currently masked because these 4 test files are not in the CI gate path.
- Likely requires either (a) substrate to restore the old API, or (b) factory to adapt to the new dict-based API.
