from __future__ import annotations

import json
import logging
import re
import subprocess
from pathlib import Path

from factory.channel import InvocationResult
from factory.config import FactoryConfig

log = logging.getLogger(__name__)


def _extract_artifact_from_output(content: str) -> str | None:
    match = re.search(r"```python\s*\n(.*?)```", content, re.DOTALL)
    if match:
        return match.group(1).rstrip()
    match = re.search(r"```\s*\n(.*?)```", content, re.DOTALL)
    if match:
        return match.group(1).rstrip()
    for i, line in enumerate(content.split("\n")):
        stripped = line.strip()
        if stripped.startswith(("from ", "import ", "class ", "def ", "@", "# ")):
            return "\n".join(content.split("\n")[i:]).rstrip()
    return None


def _extract_json_from_output(content: str) -> dict | None:
    match = re.search(r"```json\s*\n(.*?)```", content, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass
    for m in re.finditer(r"\{[\s\S]*?\}", content):
        try:
            return json.loads(m.group())
        except json.JSONDecodeError:
            continue
    return None


class ClaudeCodeChannel:
    def __init__(self, config: FactoryConfig):
        self._config = config
        self._family = "anthropic"

    @property
    def name(self) -> str:
        return "claude-code"

    @property
    def family(self) -> str:
        return self._family

    def invoke(
        self,
        role: str,
        prompt: str,
        inputs_dir: Path,
        outputs_dir: Path,
        timeout: int,
    ) -> InvocationResult:
        outputs_dir.mkdir(parents=True, exist_ok=True)
        role_config = self._config.get_role_config(role)
        effective_timeout = role_config.timeout_seconds if role_config else timeout

        try:
            result = subprocess.run(
                [
                    "claude",
                    "--print",
                    "--output-format",
                    "text",
                    "--max-turns",
                    "1",
                ],
                input=prompt,
                capture_output=True,
                text=True,
                timeout=effective_timeout,
                cwd=str(outputs_dir),
            )
        except subprocess.TimeoutExpired:
            return InvocationResult(
                success=False,
                error_message=f"Timeout after {effective_timeout}s",
                exit_code=None,
                timed_out=True,
            )
        except FileNotFoundError:
            return InvocationResult(
                success=False,
                error_message="claude not found in PATH",
                exit_code=None,
            )

        if result.returncode != 0:
            return InvocationResult(
                success=False,
                error_message=result.stderr[:2000] if result.stderr else "Non-zero exit code",
                exit_code=result.returncode,
            )

        output_text = result.stdout
        raw_path = outputs_dir / "raw_stdout.txt"
        raw_path.write_text(output_text)

        if not output_text.strip():
            return InvocationResult(
                success=False,
                error_message="Empty output from claude",
                exit_code=result.returncode,
            )

        json_data = _extract_json_from_output(output_text)
        if json_data is not None and json_data.get("status") == "cannot_proceed":
            cp_path = outputs_dir / "cannot_proceed.json"
            cp_path.write_text(json.dumps(json_data, indent=2))
            return InvocationResult(
                success=False,
                artifact_name=None,
                error_message="cannot_proceed",
            )

        artifact_content = _extract_artifact_from_output(output_text)
        if artifact_content is None:
            return InvocationResult(
                success=False,
                error_message="Could not extract artifact from claude output",
                exit_code=result.returncode,
            )

        artifact_path = outputs_dir / "artifact.pyi"
        artifact_path.write_text(artifact_content + "\n")
        return InvocationResult(
            success=True,
            artifact_name="artifact.pyi",
        )
