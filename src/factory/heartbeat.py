"""BC-194: Heartbeat claims while long-running work is in flight.

A HeartbeatSession runs a daemon thread that periodically calls
``substrate.heartbeat_claim`` to keep a claim alive while the worker is
executing potentially-minute-long subprocess invocations. If the claim is
detected as stolen (``CLAIM_LOST``), the session's ``cancel_event`` is set,
signaling cooperating subprocess wrappers and post-processing code to bail
out instead of operating on a work item that another worker now owns.

Use as a context manager::

    with HeartbeatSession(sub, wi.work_item_id, actor_id,
                          claim.attempt_number, ttl_seconds) as hb:
        result = channel.invoke(..., cancel_event=hb.cancel_event)
        if hb.cancel_event.is_set():
            return  # claim was stolen mid-flight; do not transition state
        sub.transition(...)
"""

from __future__ import annotations

import threading
import uuid
from typing import TYPE_CHECKING

import structlog
from substrate._errors import ErrorCode, SubstrateError

if TYPE_CHECKING:
    from substrate import Substrate

log = structlog.get_logger()

_MIN_INTERVAL_SECONDS = 30


class HeartbeatSession:
    def __init__(
        self,
        sub: Substrate,
        work_item_id: uuid.UUID,
        actor_id: str,
        attempt_number: int,
        ttl_seconds: int,
        interval_seconds: float | None = None,
    ) -> None:
        self._sub = sub
        self._wi_id = work_item_id
        self._actor_id = actor_id
        self._attempt = attempt_number
        self._ttl = ttl_seconds
        self._interval = interval_seconds or max(_MIN_INTERVAL_SECONDS, ttl_seconds // 3)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.cancel_event = threading.Event()

    def _beat(self) -> None:
        while not self._stop.wait(self._interval):
            try:
                self._sub.heartbeat_claim(
                    self._wi_id,
                    self._actor_id,
                    self._ttl,
                    expected_attempt_number=self._attempt,
                )
            except SubstrateError as exc:
                if exc.code == ErrorCode.CLAIM_LOST:
                    log.error(
                        "claim_lost",
                        work_item_id=str(self._wi_id),
                        actor_id=self._actor_id,
                        attempt=self._attempt,
                    )
                    self.cancel_event.set()
                    return
                log.warning(
                    "heartbeat_substrate_error",
                    work_item_id=str(self._wi_id),
                    code=str(exc.code),
                    message=exc.message,
                )
            except Exception:
                log.exception(
                    "heartbeat_unexpected_error",
                    work_item_id=str(self._wi_id),
                )

    def __enter__(self) -> HeartbeatSession:
        self._thread = threading.Thread(
            target=self._beat,
            name=f"heartbeat-{self._wi_id}",
            daemon=True,
        )
        self._thread.start()
        return self

    def __exit__(self, _exc_type, _exc, _tb) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
