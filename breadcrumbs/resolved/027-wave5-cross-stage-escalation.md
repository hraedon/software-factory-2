---
number: "027"
title: "Wave 5 — cross-stage escalation routing"
severity: high
status: implemented
kind: design
author: session-8
date: "2026-05-07"
tags: [failure-routing, gate, stage-2, stage-4]
resolution: escalation-in-router-with-attempt-threshold
---

## Background

Phase 2 plan Wave 5 required: when a test_author or implementer gate fails `attempt_threshold` times (default 3), the failure should escalate to `interface_architect` with a `cannot_proceed_seam` diagnostic, per spec §4 "ambiguous contract" failure mode. Prior to this, the router had no escalation path — test/impl failures would loop back to the same role indefinitely.

## Fix applied (2026-05-07)

1. Added `CANNOT_PROCEED_SEAM` to `DiagnosticKind`.
2. Added `_ESCALATABLE_KINDS` set containing all `IMPL_*` and `TEST_*` diagnostic kinds.
3. Extended `route()` to accept `attempt_number` and `attempt_threshold` parameters.
4. When a gate_fail with an escalatable kind meets the threshold, routing overrides the target to `interface_architect` with `cannot_proceed_seam` diagnostic, preserving the original failure diagnostics and the `escalated_from_kind` metadata.
5. Updated `gate_process.py` to pass `claim.attempt_number` and `config.attempt_threshold` through to `route()`.

Interface-architect failures are not in the escalation set — they already route to interface_architect.

Tests in `test_router_phase2.py` (12 tests covering all dispatch entries, escalation behavior, and dispatch completeness).
