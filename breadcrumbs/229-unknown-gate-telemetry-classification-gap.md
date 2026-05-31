---
number: "229"
title: "Unknown-gate rate regressed to 4.9% in GR-057 — a gate name telemetry's known-set doesn't classify"
severity: low
status: proposed
kind: bug
author: claude-opus (GR-057 review session)
date: "2026-05-31"
tags: [telemetry, gate, stage-7]
related: ["227"]
---

## Symptom

GR-057 exit criteria reported **Unknown gate rate: 4.9% (2/41) FAIL** (target
<1%); GR-056 had 0%. The per-(role,channel,model,gate) telemetry table shows a
literal `unknown / unknown / unknown / unknown` row (1 item, 0%). So 1–2 gate
events could not be bucketed by `factory.telemetry`'s gate classifier.

## Likely cause (hypothesis, not yet confirmed)

A gate name reaching the event log that telemetry's known-gate set doesn't map.
Two candidates introduced/exercised around GR-056/057:

1. **WS-2 boot probe at the implementation gate.** `gate_process.py` now runs
   `evaluate_module_boot_probe` (emitting `GATE_NAME_CONFORMANCE` /
   `DiagnosticKind.BOOT_PROBE`) at `WORK_ITEM_TYPE_IMPLEMENTATION`. Telemetry may
   not expect the `(implementer, conformance)` role/gate combo (conformance
   historically only appears at `outcome_verification`), so it falls to
   `unknown`.
2. **New `test_suite_collect` / `inner_test_collect` gate names** appeared in
   GR-057 (test-collection failure mode). If `GATE_NAME_*_COLLECT` for the
   test-suite stage isn't in telemetry's import/known list, it won't classify.

This is a **telemetry-completeness gap, not a pipeline correctness bug** — the
gates ran and recorded correctly; telemetry just can't categorize the event.

## Fix (directions)

Identify the exact unmatched event (e.g. query the GR-057 `change_log` /
gate events for the gate name on the `unknown` row), then register it in
`factory.telemetry`'s known-gate classification (and the `(role, gate)` mapping
if WS-2's conformance-at-implementation is the cause). Re-run telemetry `--verify`
to confirm unknown-gate rate returns to 0%.

## Why this isn't the previous fix recurring

N/A — first instance of this specific unknown-gate regression. Shares the
`telemetry` tag with resolved BC-068 (telemetry event-matching) but is a distinct
mechanism (new gate name vs. event-matching logic). Surfaced by the WS-1/WS-2
work tracked in BC-227.
