---
number: "005"
title: "Spec content resolution for context derivation"
severity: high
status: resolved
kind: design
author: opencode
date: "2026-05-06"
tags: [runner, stage-2, context]
related: ["002"]
---

## Problem

`derive_context()` reads `spec_section` from the work-item's `custom_fields` and uses it as the `spec_section` in the `PromptContext`. For real execution, this field contains a section identifier (e.g., `"§3.2 — acquire_claim"`) or is empty — not the actual spec text the `interface_architect` needs to produce a contract.

The `spec_content` parameter on `derive_context()` allows test overrides, but there is no production path that resolves a section identifier to actual spec content.

## Resolution

Added `spec_file: Path | None` to `FactoryConfig`. The runner loads the spec file once at startup (`_load_spec()`) and passes the content through `worker_loop → process_work_item → derive_context()`.

**Phase 1 behavior:**
- If `spec_file` is set and exists: full spec content is loaded and passed to `derive_context()`. The work-item's `spec_section` custom field is used as a section identifier or ignored (the full spec is available).
- If `spec_file` is None: `spec_section` from custom fields is used as-is (current test behavior).

**Phase 2 need:** Section extraction. When the spec is large, the interface architect should receive only the relevant section, not the full document. This requires a section extractor that splits by markdown headings and selects by the `spec_section` identifier. Deferred — Phase 1's curated test set uses inline spec content in custom fields.

**Changes:**
- `src/factory/config.py`: added `spec_file` field
- `src/factory/runner.py`: `_load_spec()`, `spec_content` parameter threading through `worker_loop` and `process_work_item`
