"""RFC-011: Unified subprocess execution layer for factory gate and runner calls.

All gate/runner subprocess calls flow through this wrapper.  cwd and env are
required to make implicit-inheritance footguns impossible at call time.  Omitting
either raises TypeError before any process is spawned — turning the BC-187 class
of bug (cwd inherited from caller) and the BC-059 class (no timeout) into
compile-time-equivalent errors rather than runtime surprises discovered in golden
run logs.
"""

from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class SubprocessResult:
    """Typed result of a subprocess invocation."""

    returncode: int
    stdout: str
    stderr: str
    duration_s: float
    timed_out: bool


def run(
    *,
    cmd: list[str],
    cwd: Path,
    env: dict[str, str],
    timeout_s: float,
    stdin: str | None = None,
    capture: bool = True,
) -> SubprocessResult:
    """Run *cmd* in a controlled subprocess and return a :class:`SubprocessResult`.

    All parameters that affect the execution environment are keyword-only with no
    defaults so that omitting any of them raises ``TypeError`` at call time.

    Args:
        cmd: The command and arguments to execute.
        cwd: Working directory for the subprocess.  Required — no implicit
            inheritance of the caller's cwd.
        env: Complete environment mapping for the subprocess.  Required — pass
            ``{}`` for a fully clean environment or use
            ``factory.sandbox.gate_subprocess_env()`` for the standard gate
            baseline.  No implicit ``os.environ`` inheritance.
        timeout_s: Maximum wall-clock seconds before the process is killed.
            Required — no implicit unbounded wait.
        stdin: Optional string to write to the process stdin.
        capture: When ``True`` (default), stdout and stderr are captured and
            returned in the result.  When ``False``, they stream directly to the
            caller's stdout/stderr and the result fields are empty strings.
    """
    stdin_bytes: bytes | None = stdin.encode() if stdin is not None else None

    stdout_pipe = subprocess.PIPE if capture else None
    stderr_pipe = subprocess.PIPE if capture else None

    t0 = time.monotonic()
    try:
        completed = subprocess.run(
            cmd,
            cwd=cwd,
            env=env if env else None,
            input=stdin_bytes,
            stdout=stdout_pipe,
            stderr=stderr_pipe,
            timeout=timeout_s,
        )
        duration = time.monotonic() - t0
        if capture:
            out = completed.stdout.decode("utf-8", errors="replace") if completed.stdout else ""
            err = completed.stderr.decode("utf-8", errors="replace") if completed.stderr else ""
        else:
            out = ""
            err = ""
        return SubprocessResult(
            returncode=completed.returncode,
            stdout=out,
            stderr=err,
            duration_s=duration,
            timed_out=False,
        )
    except subprocess.TimeoutExpired:
        duration = time.monotonic() - t0
        return SubprocessResult(
            returncode=-1,
            stdout="",
            stderr="",
            duration_s=duration,
            timed_out=True,
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
        )


def clean_env() -> dict[str, str]:
    """Return a minimal safe environment (PATH, HOME, TMPDIR, LANG).

    Call sites that need additional variables should extend this dict explicitly
    rather than inheriting ``os.environ``.
    """
    import os

    result: dict[str, str] = {}
    for key in ("PATH", "HOME", "TMPDIR", "LANG"):
        value = os.environ.get(key)
        if value is not None:
            result[key] = value
    return result
