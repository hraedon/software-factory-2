---
number: "015"
title: "Integration test private substrate API coupling"
severity: medium
status: proposed
kind: improvement
author: test-audit
date: "2026-05-07"
tags: [tests, stage-1]
---

## Background

Integration tests in `test_runner_smoke.py:81` and `test_gate_process.py:44` construct `FactoryConfig` by accessing private substrate internals:

```python
config = FactoryConfig(
    dsn=substrate._mgr._dsn,
    project_name=substrate._project,
    ...
)
```

If substrate refactors its internal manager or project storage, these tests break silently or with confusing errors.

## Acceptance criteria

- Substrate exposes a public API for retrieving DSN and project name from an existing Substrate instance (e.g., `sub.dsn`, `sub.project_name` properties).
- Integration tests use the public API instead of private attributes.