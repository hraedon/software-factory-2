---
number: "226"
title: "spec_lint should reject non-concrete ACs — fuzzy items in acceptance_criteria silently degrade RFC-038 gate coverage"
severity: medium
status: implemented
kind: improvement
author: mimo-v2.5-pro
date: "2026-05-29"
tags: [spec-lint, gates, rfc-038, phase-6]
related: ["RFC-038", "127", "130"]
---

## Context

RFC-038's AC translatability measurement (2026-05-29) found 28/28 acceptance_criteria across the three buildable fixtures are mechanically translatable — because the spec format already quarantines judgment-requiring items into `untestable_items` and `nfr` sections. This is the gate's coverage ceiling.

However, there is no enforcement that the `acceptance_criteria` section *stays* concrete. If a future spec's `acceptance_criteria` carries fuzzy items (e.g., "the response should be user-friendly" or "performance should be acceptable"), the translatable fraction drops silently and the gate's coverage degrades without detection.

## Fix

Add a `check_ac_concreteness` function to `src/factory/spec_lint.py` that flags ACs lacking concrete, observable assertions. An AC is "concrete" if it contains at least one of: an HTTP status code, a specific return value or shape, a named exception type, a numeric comparison, a string match, or a file/output pattern. ACs that only describe subjective quality ("user-friendly", "readable", "performant") or use vague qualifiers ("should", "appropriately") are flagged as WARN.

This is the preventive counterpart to RFC-038's detective approach — it catches degraded ACs at spec-authoring time rather than at verification time.

## Fix

Added `check_ac_concreteness()` to `src/factory/spec_lint.py`. The function checks each AC for concrete, observable assertions: HTTP status codes, specific return values, named exception types, numeric comparisons, code references in backticks, and structured data patterns. ACs that use vague qualifiers ("user-friendly", "readable", "performant") without any concrete assertion are flagged as WARN. ACs that lack any concrete assertion at all are also flagged as WARN. Wired into `spec_lint()` alongside the existing checks. 8 new tests.
