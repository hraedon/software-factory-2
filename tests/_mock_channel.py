from __future__ import annotations

import shutil
from pathlib import Path

from factory.channel import InvocationResult


class MockChannel:
    def __init__(self, fixtures_dir: Path, name: str = "mock", family: str = "test"):
        self._fixtures_dir = fixtures_dir
        self._name = name
        self._family = family
        self._fail_at_attempt: dict[str, int] = {}
        self._call_log: list[tuple[str, str, Path, Path]] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def family(self) -> str:
        return self._family

    def scripted_failure(self, role: str, attempt_number: int) -> None:
        self._fail_at_attempt[role] = attempt_number

    def invoke(
        self,
        role: str,
        prompt: str,
        inputs_dir: Path,
        outputs_dir: Path,
        timeout: int,
    ) -> InvocationResult:
        self._call_log.append((role, prompt, inputs_dir, outputs_dir))

        if role in self._fail_at_attempt:
            call_index = sum(1 for c in self._call_log if c[0] == role)
            if call_index == self._fail_at_attempt[role]:
                return InvocationResult(
                    success=False,
                    error_message=f"scripted_failure on attempt {call_index}",
                    exit_code=1,
                )

        fixture_dir = self._fixtures_dir / role
        cannot_proceed = fixture_dir / "cannot_proceed.json"
        if cannot_proceed.exists():
            outputs_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(cannot_proceed, outputs_dir / "cannot_proceed.json")
            return InvocationResult(
                success=False,
                artifact_name=None,
                error_message="cannot_proceed",
            )

        artifact_file = fixture_dir / "artifact.pyi"
        if not artifact_file.exists():
            artifact_file = fixture_dir / "artifact.py"
        if not artifact_file.exists():
            for candidate in sorted(fixture_dir.iterdir()):
                if candidate.is_file() and candidate.suffix in (".pyi", ".py", ".json"):
                    artifact_file = candidate
                    break

        outputs_dir.mkdir(parents=True, exist_ok=True)
        dest = outputs_dir / artifact_file.name
        shutil.copy2(artifact_file, dest)

        return InvocationResult(
            success=True,
            artifact_name=artifact_file.name,
        )

    @property
    def call_log(self) -> list[tuple[str, str, Path, Path]]:
        return list(self._call_log)
