from __future__ import annotations

import json
import logging
import subprocess
import tempfile
from pathlib import Path

from factory.channel import InvocationResult
from factory.config import FactoryConfig

log = logging.getLogger(__name__)


class ClaudeCodeChannel:
    def __init__(self, config: FactoryConfig):
        self._config = config
        self._name = "claude-code"
        self._family = "anthropic"

    @property
    def name(self) -> str:
        return self._name

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

        with tempfile.TemporaryDirectory() as tmpdir:
            prompt_file = Path(tmpdir) / "prompt.md"
            prompt_file.write_text(prompt)
            project_dir = inputs_dir if inputs_dir.exists() else Path(tmpdir)
            try:
                result = subprocess.run(
                    [
                        "claude-code",
                        "--print",
                        "--output-format",
                        "text",
                        "--max-turns",
                        "30",
                    ],
                    input=prompt,
                    capture_output=True,
                    text=True,
                    timeout=effective_timeout,
                    cwd=str(project_dir),
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
                    error_message="claude-code not found in PATH",
                    exit_code=None,
                )

            if result.returncode != 0:
                return InvocationResult(
                    success=False,
                    error_message=result.stderr[:2000] if result.stderr else "Non-zero exit code",
                    exit_code=result.returncode,
                )

            output_text = result.stdout
            if not output_text.strip():
                return InvocationResult(
                    success=False,
                    error_message="Empty output from claude-code",
                    exit_code=result.returncode,
                )

            cannot_proceed_marker = '{"status": "cannot_proceed"'
            if cannot_proceed_marker in output_text[:500]:
                start = output_text.find("{")
                end = output_text.rfind("}") + 1
                if start >= 0 and end > start:
                    try:
                        json.loads(output_text[start:end])
                        cp_path = outputs_dir / "cannot_proceed.json"
                        cp_path.write_text(output_text[start:end])
                        return InvocationResult(
                            success=False,
                            artifact_name=None,
                            error_message="cannot_proceed",
                        )
                    except json.JSONDecodeError:
                        pass

            artifact_name = self._detect_artifact_type(output_text)
            artifact_path = outputs_dir / artifact_name
            artifact_path.write_text(output_text)
            return InvocationResult(
                success=True,
                artifact_name=artifact_name,
            )

    def _detect_artifact_type(self, content: str) -> str:
        return "artifact.pyi"
