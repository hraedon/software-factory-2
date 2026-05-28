---
number: "194"
title: "No heartbeat on long-running model claims — claim theft risk"
severity: high
status: implemented
kind: bug
author: external-review
date: "2026-05-22"
tags: [runner, gate, race, failure-routing]
related: []
---

# BC-194 — No heartbeat on long-running model claims

## Problem

Model invocations in `runner.py` and gate processing in `gate_process.py` can take 1–10 minutes per work item, but claims default to a 300s TTL. With no heartbeat, the claim expires while the worker is still running. A peer worker can then steal the claim, leading to double-processing: two workers each produce an artifact, transition the work item, and emit events for what is supposed to be a single attempt.

## Resolution

Implemented as "abort on stolen claim" (vs. the simpler log-only variant): when a claim is detected as stolen mid-flight, the in-flight subprocess is killed and the worker bails out before performing any state-changing transitions.

### `factory/heartbeat.py` — HeartbeatSession (new)

Context manager that wraps a long-running claim. Spawns a daemon thread that calls `regista.heartbeat_claim(work_item_id, actor_id, ttl_seconds, expected_attempt_number=...)` every `max(30s, ttl/3)`. Behavior:

- Normal renewal: no event emitted (regista's `coalesce_threshold` suppresses spam).
- `SubstrateError(CLAIM_LOST)`: logs `claim_lost`, sets `cancel_event`, exits the thread.
- Other `SubstrateError`: logs `heartbeat_substrate_error` and keeps trying.
- Unexpected exception: logs and keeps trying — heartbeat failure must not kill the worker on transient DB blips.

The session exposes a `threading.Event` (`cancel_event`) that downstream code uses both as the kill-signal source and as a "should I keep going?" check.

### `factory/subprocess.py:run` — Popen + cancel-event polling

Refactored from `subprocess.run` (one-shot, no cancellation) to `subprocess.Popen` + `communicate(timeout=poll_interval)` loop. New optional kwarg `cancel_event: threading.Event | None`. When `None` (the default), behavior matches the historical path. When set, the loop polls the event every 500ms; on cancel, the process group is sent SIGTERM (then SIGKILL after 5s grace). Added `cancelled: bool` field to `SubprocessResult`. Process is launched with `start_new_session=True` so the whole tree of model-side subprocesses dies on SIGTERM, not just the top-level CLI.

### Channel Protocol and channels

- `factory/channel.py`: `Channel.invoke` Protocol grows an optional `cancel_event` parameter.
- `factory/subprocess_channel.py`: accepts and forwards `cancel_event` into `run_subprocess`; on `result.cancelled`, returns `InvocationResult(success=False, error_message="cancelled (claim lost)")`.
- `factory/gemini_channel.py`: accepts and forwards `cancel_event` to the parent `invoke`.

### Runner and gate process wiring

- `runner.py`: `worker_loop` wraps each `process_work_item(...)` call in a `HeartbeatSession`. `process_work_item` accepts an optional `cancel_event` and passes it into `channel.invoke` (and the fallback channel). After invocation, checks `cancel_event.is_set()` and `return`s without transitioning state if the claim was stolen mid-flight. The post-error `release_claim` is now wrapped to swallow `CLAIM_LOST` (the new owner already released).
- `gate_process.py`: `gate_loop` wraps each `process_gate_item(...)` call in a `HeartbeatSession`. `process_gate_item` accepts `cancel_event` and checks it before the final routing/transition step. The `release_claim` on the non-escalation crash path is wrapped to swallow `CLAIM_LOST`. Note: deterministic gate subprocesses (mypy, ruff, pytest) are *not* yet plumbed with `cancel_event` — the cancel check at the routing boundary prevents the worst harm (writing stolen state) but does not yet kill an in-flight pytest. See "Follow-up scope" below.
- `jury_orchestrator.py`: `_process_jury_work_item` accepts `cancel_event` and checks it both on the jury-invocation-exception path and before writing the verdict / transitioning to `submit`.

### Channel-invoke backwards compatibility

The Protocol change `cancel_event: threading.Event | None = None` is backward-compatible at type-check time but breaks runtime call sites that pass `cancel_event=` to mock channels not declared with that kwarg. To minimize test churn, `runner.py` constructs the invoke kwargs conditionally: `cancel_event` is only added when non-None, so the production call site degrades gracefully against mocks. Three mock helpers in `tests/test_gate_process_budget_and_field_validation.py` were updated to accept `**_kwargs` for the same reason. Other mock channels were left as-is.

## Tests

`tests/test_bc194_heartbeat.py` covers:

- HeartbeatSession beats periodically while in scope.
- HeartbeatSession sets `cancel_event` on `CLAIM_LOST`.
- HeartbeatSession tolerates transient (non-`CLAIM_LOST`) regista errors without cancelling.
- `subprocess.run` with `cancel_event` kills a long-running subprocess promptly when the event is set.
- `subprocess.run` without `cancel_event` is unchanged (success and timeout paths).

Full sf2 suite (excluding postgres-integration golden runs): **1052 passed, 13 skipped**.

## Follow-up scope (deliberately not in this BC)

1. **Gate subprocess cancellation.** Plumbing `cancel_event` from `process_gate_item` down through `evaluate_test_suite` / `evaluate_implementation` / etc. into the individual mypy/ruff/pytest `run_subprocess` calls. Would let an in-flight pytest be killed when its claim is stolen, not just refused at the transition boundary. Touches a half-dozen gate evaluators; should be its own BC.
2. **Jury subprocess cancellation.** `_invoke_juror` in `jury.py` and `run_jury` itself do not yet take `cancel_event`. Today the check sits at the verdict-write boundary. Same plumbing pattern as the runner side; deferred.
3. **Mock channel signatures.** Many test files declare mock channels with explicit `def invoke(self, role, prompt, outputs_dir, timeout, extra_env=None):` signatures that will break the next time the Protocol grows a kwarg. A small refactor pass to add `**_kwargs` (or to expose a `BaseMockChannel` superclass) would prevent the next round of broken tests.
