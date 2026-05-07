---
number: "012"
title: "Context derivation tests should exercise both spec_file=None and spec_file=set paths"
severity: high
status: proposed
kind: bug
author: opcode-golden-run-001
date: "2026-05-07"
tags: [runner, stage-1, context, tests]
related: ["005"]
---

## Background

`derive_context()` in `context.py` had the logic:

```python
section_content = spec_content if spec_content is not None else spec_section
```

This caused the factory's own `spec.md` to silently replace per-work-item fixture content when `spec_file` was configured. The bug was masked in all prior tests because `spec_file` was always `None` — the `spec_content` parameter was never populated.

## Root cause

`test_context.py` only exercises `_serialize_bundle()` and `PromptContext` construction — it never calls `derive_context()` with a non-None `spec_content`. The integration tests in `test_runner_smoke.py` use `MockSubstrate` which stores spec content in `custom_fields` and never passes `spec_content`.

## Fix applied

Changed logic to prefer work-item `spec_section`, only falling back to `spec_content` when `spec_section` is empty:

```python
section_content = spec_section
if not section_content and spec_content is not None:
    section_content = spec_content
```

## Acceptance criteria

- A test calls `derive_context()` with `spec_content="factory level spec"` and the work-item's `custom_fields.spec_section="work item fixture"` — asserts the work-item content is used.
- A test calls `derive_context()` with `spec_content="factory level spec"` and the work-item's `custom_fields.spec_section=""` — asserts the factory content is used as fallback.
