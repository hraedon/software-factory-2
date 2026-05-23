"""Deterministic idempotency-key generation for substrate mutations.

BC-195: All at-least-once mutation paths that can crash-and-retry must carry a
stable event_id so that duplicate substrate events are not created on retry.

Substrate enforces UUIDv4 for event_id keys (not v5, v3, etc.).  Because v4 is
random, we achieve determinism via a thread-safe in-process cache: the first
call for a given logical operation key generates a UUIDv4 and stores it;
subsequent calls with the same key return the *same* v4.  This covers the
primary failure mode (process crash between mutation and local acknowledgment
within a single process).  Cross-process restart cannot reuse the cache, so a
retry after restart may create a new event with a different UUID; that tail
risk is accepted per the "at-least-once with best-effort dedup" posture.

The cache key encodes work_item_id, transition_name, attempt_number, and an
optional extra discriminator so that logically distinct operations never
share an event_id.
"""

from __future__ import annotations

import threading
import uuid

_event_id_cache: dict[tuple[str, str, int, str], uuid.UUID] = {}
_event_id_lock = threading.Lock()

_MAX_KEY_LEN = 512  # sanity cap for key strings


def make_event_id(
    work_item_id: uuid.UUID,
    transition_name: str,
    attempt_number: int,
    extra: str = "",
) -> uuid.UUID:
    """Return a stable UUIDv4 for the logical operation described by *key*.

    First call with a given key generates a fresh UUIDv4 and caches it.
    All subsequent calls with the same key return the cached UUID.

    Usage::

        event_id = make_event_id(wi.work_item_id, TRANSITION_SUBMIT, claim.attempt_number)
        sub.transition(
            wi.work_item_id,
            TRANSITION_SUBMIT,
            actor_id,
            actor_metadata=...,
            event_id=event_id,
        )
    """
    key = (
        str(work_item_id),
        transition_name,
        attempt_number,
        extra[:_MAX_KEY_LEN],
    )
    with _event_id_lock:
        if key not in _event_id_cache:
            _event_id_cache[key] = uuid.uuid4()
        return _event_id_cache[key]


def clear_event_id(
    work_item_id: uuid.UUID,
    transition_name: str,
    attempt_number: int,
    extra: str = "",
) -> None:
    """Remove a cached event_id after a successful mutation.

    Optional: callers may clear entries to keep the cache small, but
    unbounded growth is not a concern for typical golden-run sizes
    (hundreds of entries).
    """
    key = (
        str(work_item_id),
        transition_name,
        attempt_number,
        extra[:_MAX_KEY_LEN],
    )
    with _event_id_lock:
        _event_id_cache.pop(key, None)
