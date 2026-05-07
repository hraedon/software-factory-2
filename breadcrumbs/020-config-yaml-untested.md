---
number: "020"
title: "Config YAML loading untested — from_yaml, from_yaml_or_default"
severity: low
status: proposed
kind: improvement
author: test-audit
date: "2026-05-07"
tags: [config, tests, stage-1]
---

## Background

`FactoryConfig.from_yaml` and `from_yaml_or_default` have zero test coverage. These handle YAML parsing, type coercion (list → tuple, string → Path), and fallback to defaults. A malformed YAML or missing field could crash the runner at startup with no test to catch it.

## Acceptance criteria

- Test that loads a valid YAML and asserts all fields (including `Path` coercion, tuple coercion).
- Test with a YAML missing optional fields that defaults are applied.
- Test `from_yaml_or_default` with a non-existent path returns defaults.