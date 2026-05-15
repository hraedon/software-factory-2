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


def gate_subprocess_env(**overrides: str) -> dict[str, str]:
    env = strip_sensitive_env()
    env.update(overrides)
    return env
