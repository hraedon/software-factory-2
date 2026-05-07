# DeadLetterEntry + requeue_dead_lettered_hook — ADT Validation

## Source
substrate spec §5, FR-13, FR-14

## Spec excerpt

**FR-13:** Two distinct side-effect primitives on transitions. Hook (async, durable): written to a durable `hook_queue` table on commit. Consumer woken via Postgres LISTEN/NOTIFY (latency optimization). NOTIFY payload is wakeup-only (an `event_id` reference); it is never a data channel. Polling sweep runs always at fixed default 30s interval (correctness mechanism, independent of NOTIFY). At-least-once delivery; retry-with-backoff (substrate-defined defaults). After max retries, row moves to `hook_dead_letter` table and a `hook_dead_lettered` event is emitted.

**FR-14:** Replay dead-lettered hooks via `requeue_dead_lettered_hook(id)` — resets retry counter; re-enters queue; re-failure follows same policy.

**§6 Persisted state:** `hook_queue` — pending async hooks with retry metadata. `hook_dead_letter` — terminally-failed async hooks (quarantine, replayable via FR-14).

**AC-14:** Sync hook failure rolls back the transaction; sync hook timeout triggers rollback. Async hook is enqueued; on consumer connection it is delivered; without consumer, polling sweep delivers within polling interval. Failed async hook retries per schedule; after max retries, lands in dead-letter and emits `hook_dead_lettered`.

## Work-item shape
ADT-validation — function whose contract requires defining DeadLetterEntry dataclass, HookStatus enum, and the requeue_dead_lettered_hook function signature

## AC IDs
AC-14
