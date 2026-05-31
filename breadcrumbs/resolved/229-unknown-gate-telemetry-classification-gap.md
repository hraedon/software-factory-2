---
number: "229"
title: "Unknown-gate rate regressed to 4.9% in GR-057 — a gate name telemetry's known-set doesn't classify"
severity: low
status: resolved
kind: bug
author: claude-opus (GR-057 review session)
date: "2026-05-31"
resolved: "2026-05-31"
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

## Fix

**Actual root cause (confirmed from GR-057 data):** Neither of the two
hypothesized candidates was the culprit. The 2 unknown-gate events were
`channel_fail` transitions on work item `fde76b3c` (an `implementer`/`opencode`
worker that crashed before any gate ran — opencode exited with empty output
because the agent-wake config file `/home/itadmin/.config/agent-wake/config-opencode.json`
was missing). The `channel_fail` payload had `exit_code`, `timed_out`,
`error_message`, and `duration_seconds` but **no `gate_name` field**. The
`collect_gate_attempts` code correctly checked `actor_metadata` and then
`diagnostics` for a `gate_name`, found nothing, and fell through to
`GATE_NAME_UNKNOWN`.

**Fix applied:**

1. Added `GATE_NAME_CHANNEL_FAIL = "channel_fail"` to `src/factory/constants.py`.
2. In `src/factory/telemetry.py`, imported `GATE_NAME_CHANNEL_FAIL` and added it
   to `DETERMINISTIC_GATES` (channel crashes are harness-level failures, not
   model-quality events).
3. Changed the fallback logic in `collect_gate_attempts`: when
   `ev.transition == TRANSITION_CHANNEL_FAIL` and no `gate_name` is found in
   diagnostics, classify as `GATE_NAME_CHANNEL_FAIL` instead of `GATE_NAME_UNKNOWN`.
4. Also fixed the orphan-submit detection in `run_telemetry_verify` to include
   `TRANSITION_CHANNEL_FAIL` as a gate event (so a submit+channel_fail item is
   not incorrectly flagged as an orphan).
5. Added a regression test in `tests/test_telemetry_verify.py`
   (`test_channel_fail_without_gate_name_classified_not_unknown`) that reproduces
   the exact scenario.

**Verify result after fix:**
```
unknown_gate_name_count: 0
unknown_gate_name_rate: 0.0000
orphan_submit_count: 0
unmatched_gate_count: 0
confounding_warning_count: 0
verify_passed: True
```
