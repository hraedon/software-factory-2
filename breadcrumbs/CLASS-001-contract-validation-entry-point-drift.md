---
number: "CLASS-001"
title: "JSONB / Contract Validation Entry-Point Drift"
severity: critical
status: active
kind: defect-class
author: rfc-016-backfill
date: "2026-05-15"
tags: [gate, contract, validation]
related: ["025", "034", "055", "064", "076", "089", "092", "096", "116", "146"]
---

## Shape

A validation or contract check exists in one code path but was never added to a new entry point that was introduced alongside it, so the new path silently passes invalid data.

## Systemic cause

The pipeline has many parallel execution paths (inner gate, outer gate, new role gates, per-stage evaluation functions). Each time a new validation rule or contract is added to one path, there is no mechanical mechanism that forces it to be applied to all other paths. The codebase grows by adding entry points faster than the discipline of back-propagating validation keeps up.

## Systemic fix

A shared validation registry that each gate evaluation function must consult. Adding a new rule to the registry automatically propagates it to all entry points. Alternatively, a single `evaluate_all_rules()` entry point that all gate callers invoke, instead of per-type `evaluate_<type>()` functions that independently enumerate rules.

## Trigger condition

≥5 instances (current: 10). Already justifies a systemic fix.

## Instances

| BC   | Entry Point |
|------|-------------|
| 025  | evaluate_implementation missing import/mypy/pytest/ruff gates |
| 034  | Cannot_proceed without diagnostics — double-release path |
| 055  | Stage contracts warn-and-continue instead of blocking |
| 064  | No automated channel adapter integration tests |
| 076  | Stub bodies treated as runtime deps in dep resolution path |
| 089  | .pyi stub gate allows docstring-only bodies |
| 092  | SyntaxError swallowed in gate import checks |
| 096  | populate_work_items --reset permits arbitrary directory deletion |
| 116  | _check_assertion_count returns passed=True on SyntaxError |
| 146  | test_suite_assertions gate false-negative on pytest.raises |