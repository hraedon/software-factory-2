---
number: "063"
title: "InMemorySubstrate drift history — integration test surface is 10x smaller than unit test surface"
severity: medium
status: resolved
kind: design
author: adversarial-reviewer
date: "2026-05-08"
tags: [dep-substrate-*, runner, gate]
related: ["018", "030", "035", "036"]
---

## Summary

~270 unit tests use `InMemorySubstrate`. ~10 integration tests hit real Postgres Substrate. The in-memory backend has a documented history of behavioral divergence (BC-040, BC-048, BC-050, BC-051, BC-054 on the substrate side; BC-018, BC-030, BC-035, BC-036 on the factory side).

Golden-run-002 found two bugs that all 200+ unit tests missed:
- Cross-work-item module resolution (tests used same-directory import patterns)
- Escalation routing no-op (tests didn't exercise the full state machine with real Substrate)

## Resolution

1. **`make integration` target added** — runs all `@pytest.mark.integration` tests against real Postgres. 16 integration tests pass (8 new + 8 pre-existing).

2. **`test_integration_pipeline_shapes.py`** — 8 new integration tests covering previously-untested shapes on real Postgres:
   - Test suite full lifecycle (claim → submit → gate pass)
   - Test suite gate fail returns to new
   - Implementation full 3-role chain (interface_spec → test_suite → implementation)
   - Scheduler DAG creation after lock
   - Scheduler idempotency on repeated calls
   - Channel failure → new → re-claim cycle
   - Channel failure event ordering
   - Crash recovery resume on real substrate

3. **`make replay`** deferred — not needed for Phase 3; golden-run artifact replay is low-priority versus forward-looking integration coverage.
