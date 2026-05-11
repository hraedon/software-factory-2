---
number: "111"
title: No path traversal tests for custom_fields
description: >
  dep_resolution.py, gate_process.py, and runner.py construct Path objects from
  substrate custom_fields strings. There are no tests verifying behavior when a
  custom field contains ../../../etc/passwd or null bytes.
severity: medium
status: implemented
kind: improvement
author: opencode-adversarial-review
date: "2026-05-11"
tags: [tests, security, path-traversal]
---

## Proposed fix

Add tests that inject malicious paths into custom_fields and assert the factory
rejects or sanitizes them rather than reading/writing outside the workspace.

## Affected files

- `tests/test_dep_resolution.py` (new cases)
- `tests/test_gate_process.py` (new cases)
- `tests/test_runner_unit.py` (new cases)

## Resolution

Added `_safe_artifact_path` rejecting `..` path components; added `test_path_traversal.py` with coverage for malicious custom_fields paths.
