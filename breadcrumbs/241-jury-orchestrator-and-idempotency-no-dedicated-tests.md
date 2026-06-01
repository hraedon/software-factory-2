---
number: "241"
title: "jury_orchestrator.py and idempotency.py lack dedicated test files — regression risk on jury dispatch and event-id stability"
severity: medium
status: proposed
kind: improvement
author: session-eval
date: "2026-06-01"
tags: [testing, coverage, jury, idempotency, class-014]
related: ["CLASS-014", "BC-195", "RFC-036"]
---

## Context

Two production modules have no dedicated test file:

1. **`jury_orchestrator.py`** (split from runner.py via RFC-036): Contains `_process_jury_work_item()`, which orchestrates parallel model invocations, builds jury aggregate, and routes disagreements. Only 2 indirect references in `test_runner_unit.py`. No tests for:
   - Parallel juror invocation with mixed pass/fail
   - Disagreement rationale population on split verdicts
   - Fallback channel handling for individual jurors
   - Aggregate gate_name/diagnostic_kind correctness

2. **`idempotency.py`** (created via BC-195): Contains `make_event_id()` with thread-safe UUID cache. Tested indirectly through scheduler and runner tests but no unit tests for:
   - Cache size bounds (MAX_CACHE_SIZE = 8192)
   - FIFO eviction behavior
   - Thread-safety under concurrent access
   - Same-key stability across calls

Both modules are load-bearing for Phase 5+ pipeline correctness. Regressions in either would currently be caught only by full golden runs.

## Proposed fix

Add dedicated test files:
- `tests/test_jury_orchestrator.py` — unit tests with FakeChannel covering parallel invocation, split verdicts, disagreement rationale, fallback
- `tests/test_idempotency.py` — unit tests for make_event_id stability, cache bounds, thread safety
