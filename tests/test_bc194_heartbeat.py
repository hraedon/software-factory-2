"""BC-194: HeartbeatSession lifecycle, claim-loss detection, and subprocess
cancellation through factory.subprocess.run.
"""

from __future__ import annotations

import threading
import time
import uuid
from pathlib import Path

from substrate._errors import ErrorCode, SubstrateError

from factory.heartbeat import HeartbeatSession
from factory.subprocess import run as run_subprocess


class _StubSubstrate:
    def __init__(
        self, raise_on_call: int | None = None, raise_code: ErrorCode = ErrorCode.CLAIM_LOST
    ) -> None:
        self.calls: list[tuple] = []
        self._raise_on_call = raise_on_call
        self._raise_code = raise_code
        self._lock = threading.Lock()

    def heartbeat_claim(self, work_item_id, actor_id, ttl_seconds, *, expected_attempt_number=None):
        with self._lock:
            self.calls.append((work_item_id, actor_id, ttl_seconds, expected_attempt_number))
            n = len(self.calls)
        if self._raise_on_call is not None and n >= self._raise_on_call:
            raise SubstrateError(self._raise_code, "claim lost", None)
        return None


def test_heartbeat_session_periodic_beats():
    sub = _StubSubstrate()
    wi_id = uuid.uuid4()
    with HeartbeatSession(sub, wi_id, "actor-x", 1, ttl_seconds=300, interval_seconds=0.05):
        time.sleep(0.18)
    assert len(sub.calls) >= 2
    assert all(c[0] == wi_id and c[1] == "actor-x" for c in sub.calls)
    assert all(c[3] == 1 for c in sub.calls)


def test_heartbeat_session_sets_cancel_on_claim_lost():
    sub = _StubSubstrate(raise_on_call=1)
    wi_id = uuid.uuid4()
    with HeartbeatSession(sub, wi_id, "actor-x", 1, ttl_seconds=300, interval_seconds=0.05) as hb:
        for _ in range(20):
            if hb.cancel_event.is_set():
                break
            time.sleep(0.05)
        assert hb.cancel_event.is_set()


def test_heartbeat_session_tolerates_transient_errors():
    """A non-CLAIM_LOST SubstrateError on heartbeat must not cancel work."""
    sub = _StubSubstrate(raise_on_call=1, raise_code=ErrorCode.INVALID_ARGUMENT)
    wi_id = uuid.uuid4()
    with HeartbeatSession(sub, wi_id, "actor-x", 1, ttl_seconds=300, interval_seconds=0.05) as hb:
        time.sleep(0.15)
        assert not hb.cancel_event.is_set()


def test_subprocess_run_honors_cancel_event(tmp_path: Path):
    cancel = threading.Event()

    def trip():
        time.sleep(0.3)
        cancel.set()

    t = threading.Thread(target=trip, daemon=True)
    t.start()

    result = run_subprocess(
        cmd=["sleep", "5"],
        cwd=tmp_path,
        env={"PATH": "/usr/bin:/bin"},
        timeout_s=10.0,
        cancel_event=cancel,
    )
    t.join()

    assert result.cancelled is True
    assert result.timed_out is False
    assert result.duration_s < 2.0


def test_subprocess_run_without_cancel_event_unchanged(tmp_path: Path):
    """Default behavior (no cancel_event) is unchanged: completes normally."""
    result = run_subprocess(
        cmd=["echo", "hello"],
        cwd=tmp_path,
        env={"PATH": "/usr/bin:/bin"},
        timeout_s=5.0,
    )
    assert result.returncode == 0
    assert result.cancelled is False
    assert result.timed_out is False
    assert "hello" in result.stdout


def test_subprocess_run_timeout_still_works(tmp_path: Path):
    """Timeout path is unaffected by cancel_event=None."""
    result = run_subprocess(
        cmd=["sleep", "5"],
        cwd=tmp_path,
        env={"PATH": "/usr/bin:/bin"},
        timeout_s=0.3,
    )
    assert result.timed_out is True
    assert result.cancelled is False
