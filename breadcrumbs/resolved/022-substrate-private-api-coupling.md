---
number: "022"
title: "Integration tests access substrate private API — _mgr._dsn and _project"
severity: medium
status: implemented
kind: improvement
author: test-audit
date: "2026-05-07"
tags: [tests, stage-1]
resolution: introduced-factory_config-fixture
related: ["015"]
---

## Background

Integration tests in `test_runner_smoke.py` and `test_gate_process.py` constructed `FactoryConfig` by accessing private substrate internals:

```python
config = FactoryConfig(
    dsn=substrate._mgr._dsn,
    project_name=substrate._project,
    ...
)
```

`substrate._project` is a private attribute; `substrate._mgr._dsn` is a private attribute of a private attribute. If substrate refactors its internal manager or project storage, these tests break silently or with confusing errors.

## Resolution (2026-05-07)

Added a `factory_config` pytest fixture in `conftest.py` that builds `FactoryConfig` using only public APIs:
- `DSN` is a module-level constant (known to the test suite).
- `project_name` comes from `substrate.project` (public property).
- `hmac_key_path` and `workspace_root` come from fixtures.

Updated all three integration tests in `test_runner_smoke.py` and `test_gate_process.py` to use the `factory_config` fixture instead of inline `FactoryConfig(...)` construction with private attributes.

This closes BC-015 (which has the same underlying issue) by providing the public API path. BC-015 remains open as a substrate-level request for `Substrate.dsn` to become a public property.
