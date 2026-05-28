---
number: "011"
title: "Test gap — claim transition not asserted in worker loop tests"
severity: high
status: implemented
kind: bug
author: opcode-golden-run-001
date: "2026-05-07"
tags: [stage-1, tests]
related: ["BC-003 reflection"]
resolution: added-tests
---

## Background

glm-5.1's 2026-05-06 reflection flagged: "a crash between `acquire_claim` and the `claim` transition leaves the item in a state where the claim is held but no event records it."

This sat unfixed through 67 passing tests because no test asserted the `claim` transition event was written into the event log.

## Root cause

The runner's `worker_loop` called `sub.acquire_claim()` but never called `sub.transition(wi, "claim", ...)` to progress the work-item's state from `new → in_progress`. The 5 integration tests in `test_gate_process.py` and `test_runner_smoke.py` all tested sub-components in isolation (`process_gate_item`, `process_work_item` with pre-setup state) — none exercised the full `worker_loop` path that bridges claim acquisition → state transition.

## Fix applied

Added explicit `sub.transition(wi.work_item_id, "claim", actor_id, actor_metadata=...)` call in `worker_loop` immediately after `acquire_claim` succeeds (runner.py:91-101).

## Acceptance criteria

- A test exercises `worker_loop` against `MockSubstrate` and asserts the `claim` transition event is recorded in the mock event log.
- A test exercises `worker_loop` against live regista and asserts that after `acquire_claim`, the work-item's `current_state` is `in_progress` (not `new`).

**Implemented (2026-05-07):** Added three tests:
- `TestWorkerLoopClaimTransition::test_claim_event_recorded_in_mock_substrate` — exercises full claim→transition→process path on MockSubstrate, asserts `claim` event recorded and state reaches `gating`.
- `TestWorkerLoopClaimTransition::test_worker_loop_sets_in_progress_state` — asserts work-item is in `in_progress` after claim transition on MockSubstrate.
- `TestWorkerLoopClaimTransitionLive::test_claim_transition_on_live_substrate` — integration test against live regista asserting claim event and `in_progress` state.
