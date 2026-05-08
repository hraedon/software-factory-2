---
number: "035"
title: "InMemorySubstrate get_work_item rejects string UUIDs — gate import/mypy/pytest checks silently skipped"
severity: high
status: proposed
kind: bug
author: opencode
date: "2026-05-08"
tags: [gate, dep-substrate, failure-routing, testing]
related: ["025"]
---

## Problem

`gate_process.py:99` passes `interface_ref` (a string from `custom_fields`) directly to `sub.get_work_item(interface_ref)`. InMemorySubstrate's `get_work_item` expects a `uuid.UUID` object and silently returns `None` for string arguments. The real Postgres Substrate handles string→UUID coercion transparently.

**Consequence:** every InMemory test that drives the implementation or test_suite gate never resolves `interface_pyi_path` or `test_suite_path`, so `_check_impl_imports`, `_run_mypy`, and `_run_pytest` are all silently skipped. Only syntax + ruff checks actually execute. This means:

- The `impl_import` diagnostic kind is unreachable in InMemory tests
- The `impl_mypy` diagnostic kind is unreachable in InMemory tests  
- The `impl_pytest` diagnostic kind is unreachable in InMemory tests
- Three of the seven escalatable kinds have zero end-to-end test coverage under InMemory

## Evidence

Pre-wave-7 escalation test initially asserted `impl_import` but got `impl_lint` because the import check was bypassed and ruff flagged the unused import instead.

## Fix options

(a) InMemorySubstrate: accept `str | uuid.UUID` in `get_work_item`, converting strings to UUID. This is a substrate-side fix.
(b) gate_process.py: explicitly convert ref strings to UUID before calling `get_work_item`. Factory-side fix, minimal risk.

Option (b) is preferred — it's defensive and doesn't require a substrate release.
