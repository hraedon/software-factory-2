# DriftReport — ADT Validation

## Source
substrate spec §5, FR-16, §6

## Spec excerpt

**FR-16:** Replay — rebuild a `work_items_current_replay_<timestamp>` projection from the event log on demand. Each historical transition validates against the workflow version recorded on its event. Output is a fresh table; substrate does NOT mutate live `work_items_current` in place. Operator decides whether to atomically swap (rename) or diff for verification.

Substrate also produces a companion `replay_report_<timestamp>` table categorizing each work-item:

- `replayed_ok` — replayed final state matches live `work_items_current`.
- `replayed_drift` — replayed final state differs from live. This is the actionable signal. Possible causes: bug in projection update logic, direct edit to `work_items_current` outside the substrate API (forbidden by §18), missed event (corruption — usually accompanied by `event_seq` gap).
- `halted` — replay could not complete on this work-item; halt reason recorded (`revoked_key`, `missing_workflow_version`, `unrecognized_transition`, `signature_verification_failed`, etc.).
- `warnings` — count of events skipped during signature verification (when `continue_on_revoked=True`); informational, not a defect signal.

The report is the operator's primary interface to replay. Nonzero `replayed_drift` count is a defect signal. `halted` rows are operator alerts; live projection is untouched on halt.

**AC-16:** `replay_report_<ts>` contains exactly one row per work-item processed, categorized as `replayed_ok`, `replayed_drift`, or `halted`. Drift count of zero is the success criterion for a no-bug projection. Each historical transition is validated against the workflow version recorded on its event.

## Work-item shape
ADT-validation — function whose contract requires defining structured payload types (DriftReport, ReplayCategory enum, HaltReason enum)

## AC IDs
AC-16
