---
number: "020"
title: "Config YAML loading untested — from_yaml, from_yaml_or_default"
severity: low
status: implemented
kind: improvement
author: test-audit
date: "2026-05-07"
tags: [config, tests, stage-1]
resolution: added-tests
---

## Background

`FactoryConfig.from_yaml` and `from_yaml_or_default` have zero test coverage. These handle YAML parsing, type coercion (list → tuple, string → Path), and fallback to defaults. A malformed YAML or missing field could crash the runner at startup with no test to catch it.

## Acceptance criteria

- Test that loads a valid YAML and asserts all fields (including `Path` coercion, tuple coercion).
- Test with a YAML missing optional fields that defaults are applied.
- Test `from_yaml_or_default` with a non-existent path returns defaults.

## Fix applied (2026-05-07)

Added `tests/test_config.py` with six tests:
- `test_load_valid_yaml_all_fields` — full round-trip: `Path`, tuple, `RoleConfig` coercion.
- `test_missing_optional_fields_use_defaults` — minimal YAML, defaults intact.
- `test_from_yaml_or_default_with_nonexistent_path` — returns default config.
- `test_from_yaml_or_default_with_existing_path` — loads override YAML.
- `test_from_yaml_or_default_with_none` — returns defaults when path is None.
- `test_role_config_lookup` — `get_role_config` behavior.
