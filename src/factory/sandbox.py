from __future__ import annotations

import os

_SENSITIVE_SUBSTRINGS = (
    "KEY",
    "SECRET",
    "TOKEN",
    "CREDENTIAL",
    "PASSWORD",
    "AUTH",
)

_SENSITIVE_EXACT = frozenset(
    {
        "DATABASE_URL",
    }
)


def strip_sensitive_env(
    base_env: dict[str, str] | None = None,
) -> dict[str, str]:
    source = base_env if base_env is not None else os.environ
    result: dict[str, str] = {}
    for key, value in source.items():
        upper = key.upper()
        if upper in _SENSITIVE_EXACT:
            continue
        if any(p in upper for p in _SENSITIVE_SUBSTRINGS):
            continue
        result[key] = value
    return result


def gate_subprocess_env(
    inherit_pythonpath: bool = False,
    **overrides: str,
) -> dict[str, str]:
    """Build a sanitised environment for gate subprocesses.

    Args:
        inherit_pythonpath: When False (default, hermetic), any PYTHONPATH
            inherited from the parent process is stripped before applying
            *overrides*.  Callers that genuinely need the parent's PYTHONPATH
            should pass ``inherit_pythonpath=True`` explicitly.
        **overrides: Additional environment variables to set (e.g.
            ``PYTHONPATH=str(tmp_path)`` or ``MYPYPATH=str(tmp_path)``).
            These are applied *after* the optional PYTHONPATH strip.
    """
    env = strip_sensitive_env()
    if not inherit_pythonpath:
        env.pop("PYTHONPATH", None)
        env.pop("MYPYPATH", None)
    env.update(overrides)
    return env
