from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

from factory.channel import InvocationResult
from factory.config import FactoryConfig
from factory.constants import (
    ARTIFACT_FILENAME_CANNOT_PROCEED,
    ARTIFACT_FILENAME_RAW_STDOUT,
    CHANNEL_CLAUDE_CODE,
    FAMILY_ANTHROPIC,
    ROLE_INTERFACE_ARCHITECT,
)
from factory.output_extraction import extract_artifact_from_output, extract_json_from_output

log = logging.getLogger(__name__)

# Re-export for backward compatibility with existing tests
_extract_artifact_from_output = extract_artifact_from_output
_extract_json_from_output = extract_json_from_output


class ClaudeCodeChannel:
    def __init__(self, config: FactoryConfig):
        self._config = config
        self._family_override: str | None = None

    @property
    def name(self) -> str:
        return CHANNEL_CLAUDE_CODE

    @property
    def family(self) -> str:
        if self._family_override is not None:
            return self._family_override
        return FAMILY_ANTHROPIC

    @staticmethod
    def _artifact_extension_for_role(role: str) -> str:
        if role == ROLE_INTERFACE_ARCHITECT:
            return ".pyi"
        return ".py"

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
        invocation_family = FAMILY_ANTHROPIC
        if role_config and role_config.model:
            self._family_override = FAMILY_ANTHROPIC

        cmd = [
            "claude",
            "--print",
            "--output-format",
            "text",
            "--max-turns",
            "1",
        ]
        if role_config and role_config.model:
            cmd.extend(["--model", role_config.model])
        try:
            result = subprocess.run(
                cmd,
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
                family=invocation_family,
            )
        except FileNotFoundError:
            return InvocationResult(
                success=False,
                error_message="claude not found in PATH",
                exit_code=None,
                family=invocation_family,
            )

        if result.returncode != 0:
            return InvocationResult(
                success=False,
                error_message=result.stderr[:2000] if result.stderr else "Non-zero exit code",
                exit_code=result.returncode,
                family=invocation_family,
            )

        output_text = result.stdout
        raw_path = outputs_dir / ARTIFACT_FILENAME_RAW_STDOUT
        raw_path.write_text(output_text)

        if not output_text.strip():
            return InvocationResult(
                success=False,
                error_message="Empty output from claude",
                exit_code=result.returncode,
                family=invocation_family,
            )

        json_data = _extract_json_from_output(output_text)
        if json_data is not None and json_data.get("status") == "cannot_proceed":
            cp_path = outputs_dir / ARTIFACT_FILENAME_CANNOT_PROCEED
            cp_path.write_text(json.dumps(json_data, indent=2))
            return InvocationResult(
                success=False,
                artifact_name=None,
                error_message="cannot_proceed",
                family=invocation_family,
            )

        artifact_content = _extract_artifact_from_output(output_text)
        if artifact_content is None:
            return InvocationResult(
                success=False,
                error_message="Could not extract artifact from claude output",
                exit_code=result.returncode,
                family=invocation_family,
            )

        ext = self._artifact_extension_for_role(role)
        artifact_name = f"artifact{ext}"
        artifact_path = outputs_dir / artifact_name
        artifact_path.write_text(artifact_content + "\n")
        return InvocationResult(
            success=True,
            artifact_name=artifact_name,
            family=invocation_family,
        )
