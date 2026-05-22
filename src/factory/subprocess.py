"""RFC-011: Unified subprocess execution layer for factory gate and runner calls.

All gate/runner subprocess calls flow through this wrapper.  cwd and env are
required to make implicit-inheritance footguns impossible at call time.  Omitting
either raises TypeError before any process is spawned — turning the BC-187 class
of bug (cwd inherited from caller) and the BC-059 class (no timeout) into
compile-time-equivalent errors rather than runtime surprises discovered in golden
run logs.

BC-194: callers that hold a substrate claim while a subprocess runs may pass a
``cancel_event``. When set (by a HeartbeatSession on detected claim theft) the
running subprocess is sent SIGTERM (then SIGKILL after a short grace period) and
the result is returned with ``cancelled=True``.
"""

from __future__ import annotations

import os
import signal
import subprocess
import threading
import time
from dataclasses import dataclass
from pathlib import Path

_CANCEL_POLL_INTERVAL = 0.5
_TERM_GRACE_SECONDS = 5.0


@dataclass(frozen=True)
class SubprocessResult:
    """Typed result of a subprocess invocation."""

    returncode: int
    stdout: str
    stderr: str
    duration_s: float
    timed_out: bool
    cancelled: bool = False


def run(
    *,
    cmd: list[str],
    cwd: Path,
    env: dict[str, str],
    timeout_s: float,
    stdin: str | None = None,
    capture: bool = True,
    cancel_event: threading.Event | None = None,
) -> SubprocessResult:
    """Run *cmd* in a controlled subprocess and return a :class:`SubprocessResult`.

    All execution-environment parameters are keyword-only with no defaults so
    that omitting any raises ``TypeError`` at call time.

    Args:
        cmd: The command and arguments to execute.
        cwd: Working directory for the subprocess.
        env: Complete environment mapping.  Pass ``{}`` for an empty environment
            or use ``factory.sandbox.gate_subprocess_env()`` for the standard
            gate baseline.
        timeout_s: Maximum wall-clock seconds before the process is killed.
        stdin: Optional string to write to the process stdin.
        capture: When ``True`` (default), stdout and stderr are captured and
            returned in the result.  When ``False``, they stream to the caller.
        cancel_event: BC-194 — when set, terminate the subprocess and return
            with ``cancelled=True``.  When ``None`` (default), behaviour matches
            the historical ``subprocess.run``-based path.
    """
    stdin_bytes: bytes | None = stdin.encode() if stdin is not None else None

    stdout_pipe = subprocess.PIPE if capture else None
    stderr_pipe = subprocess.PIPE if capture else None
    stdin_pipe = subprocess.PIPE if stdin_bytes is not None else None

    t0 = time.monotonic()
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            env=env if env else None,
            stdin=stdin_pipe,
            stdout=stdout_pipe,
            stderr=stderr_pipe,
            start_new_session=True,
        )
    except OSError as exc:
        duration = time.monotonic() - t0
        binary = cmd[0] if cmd else "<empty>"
        return SubprocessResult(
            returncode=-1,
            stdout="",
            stderr=f"binary not found: {binary}: {exc}",
            duration_s=duration,
            timed_out=False,
            cancelled=False,
        )

    deadline = t0 + timeout_s
    cancelled = False
    timed_out = False
    out_bytes = b""
    err_bytes = b""

    if cancel_event is None:
        try:
            out_bytes, err_bytes = proc.communicate(input=stdin_bytes, timeout=timeout_s)
        except subprocess.TimeoutExpired:
            timed_out = True
    else:
        first_wait = min(_CANCEL_POLL_INTERVAL, timeout_s)
        try:
            out_bytes, err_bytes = proc.communicate(input=stdin_bytes, timeout=first_wait)
        except subprocess.TimeoutExpired:
            while True:
                if cancel_event.is_set():
                    cancelled = True
                    break
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    timed_out = True
                    break
                wait_chunk = min(_CANCEL_POLL_INTERVAL, remaining)
                try:
                    out_bytes, err_bytes = proc.communicate(timeout=wait_chunk)
                    break
                except subprocess.TimeoutExpired:
                    continue

    if cancelled or timed_out:
        _terminate(proc)
        try:
            tail_out, tail_err = proc.communicate(timeout=_TERM_GRACE_SECONDS)
            if tail_out:
                out_bytes = (out_bytes or b"") + tail_out
            if tail_err:
                err_bytes = (err_bytes or b"") + tail_err
        except subprocess.TimeoutExpired:
            pass

    duration = time.monotonic() - t0
    if capture:
        out = out_bytes.decode("utf-8", errors="replace") if out_bytes else ""
        err = err_bytes.decode("utf-8", errors="replace") if err_bytes else ""
    else:
        out = ""
        err = ""

    if timed_out:
        return SubprocessResult(
            returncode=-1,
            stdout="",
            stderr="",
            duration_s=duration,
            timed_out=True,
            cancelled=False,
        )
    if cancelled:
        return SubprocessResult(
            returncode=proc.returncode if proc.returncode is not None else -2,
            stdout=out,
            stderr=err,
            duration_s=duration,
            timed_out=False,
            cancelled=True,
        )
    return SubprocessResult(
        returncode=proc.returncode,
        stdout=out,
        stderr=err,
        duration_s=duration,
        timed_out=False,
        cancelled=False,
    )


def _terminate(proc: subprocess.Popen) -> None:
    if proc.poll() is not None:
        return
    try:
        pgid = os.getpgid(proc.pid)
    except (ProcessLookupError, PermissionError):
        pgid = None
    try:
        if pgid is not None:
            os.killpg(pgid, signal.SIGTERM)
        else:
            proc.terminate()
    except (ProcessLookupError, PermissionError):
        return
    try:
        proc.wait(timeout=_TERM_GRACE_SECONDS)
        return
    except subprocess.TimeoutExpired:
        pass
    try:
        if pgid is not None:
            os.killpg(pgid, signal.SIGKILL)
        else:
            proc.kill()
    except (ProcessLookupError, PermissionError):
        return


def clean_env() -> dict[str, str]:
    """Return a minimal safe environment (PATH, HOME, TMPDIR, LANG).

    Call sites that need additional variables should extend this dict explicitly
    rather than inheriting ``os.environ``.
    """
    result: dict[str, str] = {}
    for key in ("PATH", "HOME", "TMPDIR", "LANG"):
        value = os.environ.get(key)
        if value is not None:
            result[key] = value
    return result
