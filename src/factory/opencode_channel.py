from __future__ import annotations

import json
import logging
import subprocess
from pathlib import Path

from factory.channel import InvocationResult
from factory.config import FactoryConfig
from factory.output_extraction import extract_artifact_from_output, extract_json_from_output

log = logging.getLogger(__name__)

# Mapping from model provider prefix to family name for telemetry.
_FAMILY_BY_PROVIDER: dict[str, str] = {
    "zai-coding-plan": "zai",
    "ollama-cloud": "ollama",
    "fireworks-ai": "fireworks",
    "opencode": "opencode-free",
    "mac-studio-lms": "local-lms",
}


def _derive_family(model: str | None) -> str:
    if not model:
        return "opencode"
    prefix = model.split("/")[0]
    return _FAMILY_BY_PROVIDER.get(prefix, prefix)


class OpenCodeChannel:
    def __init__(self, config: FactoryConfig):
        self._config = config
        self._family = "opencode"

    @property
    def name(self) -> str:
        return "opencode"

    @property
    def family(self) -> str:
        return self._family

    @staticmethod
    def _artifact_extension_for_role(role: str) -> str:
        if role == "interface_architect":
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
        model = role_config.model if role_config else None

        cmd = [
            "opencode",
            "run",
            "--dangerously-skip-permissions",
        ]
        if model:
            cmd.extend(["--model", model])
        if role_config and role_config.model:
            self._family = _derive_family(role_config.model)
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
            )
        except FileNotFoundError:
            return InvocationResult(
                success=False,
                error_message="opencode not found in PATH",
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
                error_message="Empty output from opencode",
                exit_code=result.returncode,
            )

        json_data = extract_json_from_output(output_text)
        if json_data is not None and json_data.get("status") == "cannot_proceed":
            cp_path = outputs_dir / "cannot_proceed.json"
            cp_path.write_text(json.dumps(json_data, indent=2))
            return InvocationResult(
                success=False,
                artifact_name=None,
                error_message="cannot_proceed",
            )

        artifact_content = extract_artifact_from_output(output_text)
        if artifact_content is None:
            return InvocationResult(
                success=False,
                error_message="Could not extract artifact from opencode output",
                exit_code=result.returncode,
            )

        ext = self._artifact_extension_for_role(role)
        artifact_name = f"artifact{ext}"
        artifact_path = outputs_dir / artifact_name
        artifact_path.write_text(artifact_content + "\n")
        return InvocationResult(
            success=True,
            artifact_name=artifact_name,
        )
