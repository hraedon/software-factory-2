---
number: "212"
title: "No config schema validation — invalid configs accepted without error"
severity: high
status: implemented
kind: bug
author: adversarial-review
date: "2026-05-25"
tags: [config, validation]
related: []
---

## Problem

`FactoryConfig.from_yaml()` accepted arbitrary values: `attempt_threshold` could be 0 or 10000, `poll_interval_seconds` could be negative, `dsn` could be empty. The only validation was `validate_jury_config()` which produced warnings (not errors). An invalid config could cause unbounded retry loops or database corruption.

## Fix (Session 53)

Added `FactoryConfig.validate()` method that checks:
- `attempt_threshold >= 1`
- `inner_gate_retries >= 0`
- `poll_interval_seconds > 0`
- `claim_ttl_seconds > 0`
- `jury_quorum >= 1`
- `query_page_size >= 1`
- All roles in `type_to_role` have corresponding `RoleConfig` entries

`from_yaml()` now calls `validate()` and raises `ValueError` on invalid configs. Default configs (no YAML) use safe defaults and pass validation.
