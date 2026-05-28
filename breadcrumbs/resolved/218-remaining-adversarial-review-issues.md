---
number: "218"
title: "Remaining medium-severity quality issues from adversarial review"
severity: medium
status: resolved
kind: improvement
author: adversarial-review
date: "2026-05-27"
resolved_date: "2026-05-27"
tags: [runner, telemetry, gate, CLASS-012]
related: ["217"]
---

## Summary

BC-217 fixed the critical and high issues. This BC tracked the remaining medium-severity issues. All actionable items resolved in single pass.

## What was fixed

### Unbounded in-memory caches

- `scheduler.py _existence_cache` — added `_EXISTENCE_CACHE_MAXSIZE = 4096` cap with FIFO eviction.
- `idempotency.py _event_id_cache` — added `_MAX_CACHE_SIZE = 8192` cap with FIFO eviction.
- `gate_process.py _crash_state` — already bounded (entries cleaned on item completion, local to loop).
- `context.py _gather_other_locked_artifacts` — deferred (bounded by locked item count; not a leak).

### CLASS-012 residual string constant gravity

- Moved `DiagnosticKind` enum from `router.py` to `constants.py` so gate modules can use it without circular imports.
- Replaced all 88+ bare `diagnostic_kind="..."` strings in `gate/*.py` with `DiagnosticKind` enum values.
- Added `ARTIFACT_OVERSIZED` and `INTEGRATION_UNSAFE_PATH` to the enum.
- Updated `GateResult.diagnostic_kind` type from `str` to `DiagnosticKind | str`.
- Added both new kinds to router dispatch table.
- Made `_KIND_DISPATCH` and `_ESCALATABLE_KINDS` public (renamed, with backward-compatible aliases).

### Design debt

- `pipeline_docs.py` — now imports public `KIND_DISPATCH` and `ESCALATABLE_KINDS` (backward compat aliases preserved).
- `failure_summary.py` — `gate_output` field now populated from event `diagnostics.messages`.
- `decomposer.py` — validates `yaml.safe_load()` result is a `dict`.
- `catalog.py` — validates loaded YAML is a `dict`.

## Not fixed (deferred)

- `telemetry.py compute_exit_criteria` — 160-line function decomposition. Invasive refactor, low risk.
- `initiative.py` uses `Any` type — would require typing regista's `Regista` class.
- `agent_golden_run.py` config assumption — needs validation against actual FactoryConfig format.
- `gate/test_suite.py` and `gate/implementation.py` inline forbidden-module sets — minor, not worth extracting.
- Various tempdir prefixes — cosmetic, no functional impact.
