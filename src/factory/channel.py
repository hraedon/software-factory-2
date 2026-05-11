from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class InvocationResult:
    success: bool
    artifact_name: str | None = None
    error_message: str | None = None
    exit_code: int | None = None
    timed_out: bool = False
    family: str | None = None


@runtime_checkable
class Channel(Protocol):
    name: str
    family: str

    def invoke(
        self,
        role: str,
        prompt: str,
        outputs_dir: Path,
        timeout: int,
        extra_env: dict[str, str] | None = None,
    ) -> InvocationResult: ...
