---
number: "076"
title: Dependency .pyi stub bodies are Ellipsis — gate copies stub as runtime dep, causing pytest failures
severity: high
status: implemented
kind: bug
author: opencode-glm-5.1
date: "2026-05-10"
tags: [gate, dependency, cross-module, cert-watch, stage-5]
related: ["074", "072"]
---

## Problem

When a downstream implementation's test calls a dependency's function at runtime (e.g., `parse_certificate(der)` from `certificate_model`), the gate copies the locked `.pyi` stub into the temp directory as both `.py` and `.pyi`. Stub method bodies are `...` (Ellipsis), so the call returns `Ellipsis` at runtime and the test fails `isinstance(result, Certificate)`.

This is not a model quality issue — it is a pipeline gap. The model's implementation is correct; it cannot pass the gate because the dependency module is a stub.

## Evidence

- GR-011: FR-03 `test_upload_certificate_valid_pem_returns_uploaded_entry` failed pytest on all attempts (inner gate retries 0 and 1, outer gate, escalation attempt). The test calls `parse_certificate(der)` which resolves to the `certificate_model.py` stub where `parse_certificate(...) -> ...: ...`.
- FR-02 passed because its test constructs `Certificate(subject=..., issuer=...)` directly — never exercising `parse_certificate` at runtime.
- In GR-006a, the same pattern caused all FR-02 and FR-03 tests to fail with `ModuleNotFoundError` (BC-072), which was fixed. But the runtime stub problem was masked because the inner gate's `_run_pytest` was not yet extended to include pytest (BC-075).

## Fix implemented

### 1. Dep resolution prefers locked implementations

New module `src/factory/dep_resolution.py` with `resolve_dep_artifacts()`:
- For each dependency ref, checks if the dep work item is an `interface_spec` (via `_find_locked_impl()`).
- If a locked implementation exists, uses its `.py` artifact as the runtime module and the spec's `.pyi` as the type stub.
- If no implementation is locked (stub-only), uses the spec's `.pyi` for both and marks the dep as `is_stub_only=True`.

### 2. Gate copies impl .py + spec .pyi separately

`copy_dependency_pyis()` in `pre_gate.py` now accepts an optional `dependency_spec_paths` parameter:
- When a dep has a locked implementation: writes the impl's `.py` as the runtime module and the spec's `.pyi` as the type stub for mypy.
- When a dep is stub-only: writes the same `.pyi` content as both `.py` and `.pyi` (previous behavior).

### 3. Stub-only deps surfaced in prompt

`PromptContext` now has a `stub_only_deps: list[str]` field. When dep resolution finds stub-only dependencies, `render_prompt()` adds a `## stub_only_dependencies` warning section telling the model not to call stub functions at runtime.

### 4. Scheduler ordering (not yet changed)

Opus noted that impl work-items have a real ordering constraint on each other. The scheduler already propagates `dependency_refs` verbatim, so downstream impls will find their deps' locked implementations via `_find_locked_impl()`. No scheduler change was needed for this fix.

### 5. Cert-watch full fixture

Created `/tests/fixtures/cert-watch/` with 8 work-units and a proper dependency graph:
- certificate_model (no deps) — foundation
- cert_chain_library ← certificate_model (shared utility, no FR mapping)
- database_layer ← certificate_model
- fr01_dashboard ← database_layer
- fr02_tls_scan ← certificate_model, database_layer, cert_chain_library (diamond)
- fr03_upload ← certificate_model, database_layer, cert_chain_library (diamond)
- fr04_alerts ← certificate_model, database_layer (diamond — 3rd diamond consumer of certificate_model)
- fr05_scheduler ← fr02_tls_scan, fr04_alerts (multi-hop chain)

Downstream ACs enforce runtime dep calls (not just type imports):
- fr02 AC-04: leaf must equal `parse_certificate(handshake_der)`
- fr04 AC-02: thresholds computed against `Certificate.days_until_expiry()`
- database_layer AC-02: `add(cert)` persists `cert.fingerprint_sha256`

## Scheduler implication (not yet implemented)

The scheduler currently propagates `dependency_refs` (pointing to interface_spec work items). For the dep resolution to find locked implementations, those implementations must already be locked. This means `fr03_upload`'s implementation cannot be gated until `certificate_model`'s implementation is locked. The scheduler creates implementation work items as soon as their test_suite is locked, not when their deps' implementations are locked. This is correct for the current sequential channel — the worker will wait in the claim loop until the dep implementation completes. But for parallel channels (Phase 3+), the scheduler should respect dep-impl ordering.

## Tests

- `dep_resolution.py` has unit-test-ready helpers (`_find_locked_impl`, `resolve_dep_artifacts`, `resolve_dep_refs_for_gate`, `resolve_dep_refs_for_context`)
- Existing 374 tests pass, lint clean, audit clean