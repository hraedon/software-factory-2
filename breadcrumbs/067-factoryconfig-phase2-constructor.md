---
number: "067"
title: "No FactoryConfig.phase2() constructor — requires manual setattr bypass"
severity: low
status: proposed
kind: improvement
author: adversarial-reviewer
date: "2026-05-08"
tags: [runner, config]
related: ["032", "058"]

## Summary

`FactoryConfig` is a frozen dataclass with Phase 1 defaults (single role, `interface_architect` only). Phase 2 configuration requires manually setting static class attributes after construction:

```python
config.worker_roles = FactoryConfig.PHASE2_WORKER_ROLES
config.type_to_role = FactoryConfig.PHASE2_TYPE_TO_ROLE
config.roles = FactoryConfig.PHASE2_ROLES
```

Since `FactoryConfig` is frozen, `setattr` fails unless you bypass the dataclass with `object.__setattr__` (which tests do). The YAML configuration path works correctly (populate a YAML file with the right values), but there's no programmatic shorthand.

## Fix

Add a `@classmethod`:

```python
@classmethod
def phase2(cls, **overrides) -> FactoryConfig:
    return cls(
        workflow_version=2,
        worker_roles=cls.PHASE2_WORKER_ROLES,
        type_to_role=cls.PHASE2_TYPE_TO_ROLE,
        roles=cls.PHASE2_ROLES,
        **overrides,
    )
```

Low priority — YAML config works. Convenience only. Useful for golden run config construction in tests/tools.
