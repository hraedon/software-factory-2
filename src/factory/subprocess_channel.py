from __future__ import annotations

import json
import os
import threading
import time
from pathlib import Path
from typing import ClassVar

import structlog

from factory.channel import InvocationResult
from factory.config import FactoryConfig
from factory.constants import (
    ARTIFACT_FILENAME_CANNOT_PROCEED,
    ARTIFACT_FILENAME_RAW_STDERR,
    ARTIFACT_FILENAME_RAW_STDOUT,
    MAX_ARTIFACT_SIZE_BYTES,
    ROLE_INTEGRATOR,
    ROLE_INTERFACE_ARCHITECT,
    ROLE_OUTCOME_VERIFIER,
)
from factory.output_extraction import extract_artifact_from_output, extract_json_from_output
from factory.subprocess import run as run_subprocess

_JSON_ARTIFACT_ROLES = frozenset({ROLE_INTEGRATOR, ROLE_OUTCOME_VERIFIER})

log = structlog.get_logger()


class SubprocessChannel:
    CMD: ClassVar[list[str]] = []
    _NAME: ClassVar[str] = ""
    _DEFAULT_FAMILY: ClassVar[str] = ""

    def __init__(self, config: FactoryConfig):
        self._config = config

    @property
    def name(self) -> str:
        return self._NAME

    @property
    def family(self) -> str:
        return self._DEFAULT_FAMILY

    def _derive_invocation_family(self, role_config) -> str:
        raise NotImplementedError

    def _build_cmd(self, role_config) -> list[str]:
        return list(self.CMD)

    @staticmethod
    def _artifact_extension_for_role(role: str) -> str:
        if role == ROLE_INTERFACE_ARCHITECT:
            return ".pyi"
        if role in _JSON_ARTIFACT_ROLES:
            return ".json"
        return ".py"

    def invoke(
        self,
        role: str,
        prompt: str,
        outputs_dir: Path,
        timeout: int,
        extra_env: dict[str, str] | None = None,
        model_override: str | None = None,
        cancel_event: threading.Event | None = None,
    ) -> InvocationResult:
        outputs_dir.mkdir(parents=True, exist_ok=True)
        role_config = self._config.get_role_config(role)
        effective_timeout = role_config.timeout_seconds if role_config else timeout
        model = model_override or (role_config.model if role_config else None)

        cmd = self._build_cmd(role_config)
        if model:
            cmd.extend(["--model", model])

        if model_override:
            from factory.constants import FAMILY_BY_PROVIDER

            prefix = model_override.split("/")[0]
            invocation_family = FAMILY_BY_PROVIDER.get(prefix, prefix)
        else:
            invocation_family = self._derive_invocation_family(role_config)
        # BC-187 fix: always use outputs_dir as the subprocess cwd so that any
        # files written by the model channel land in the ephemeral attempt
        # directory, not in whatever invocation_cwd points to (often repo root).
        # invocation_cwd was previously used as the subprocess cwd, which caused
        # model-generated artifacts to leak into /projects/software-factory-2.
        subprocess_cwd = outputs_dir
        env_override: dict[str, str] = {**os.environ, **(extra_env or {})}

        max_empty_retries = self._config.empty_output_retries
        retry_delay = self._config.empty_output_retry_delay_seconds
        last_stderr = ""

        for attempt in range(max_empty_retries + 1):
            result = run_subprocess(
                cmd=cmd,
                cwd=subprocess_cwd,
                env=env_override,
                timeout_s=effective_timeout,
                stdin=prompt,
                cancel_event=cancel_event,
            )
            if result.cancelled:
                return InvocationResult(
                    success=False,
                    error_message="cancelled (claim lost)",
                    exit_code=None,
                    family=invocation_family,
                    model=model,
                )
            if result.timed_out:
                return InvocationResult(
                    success=False,
                    error_message=f"Timeout after {effective_timeout}s",
                    exit_code=None,
                    timed_out=True,
                    family=invocation_family,
                    model=model,
                )
            if result.returncode == -1 and not result.timed_out:
                return InvocationResult(
                    success=False,
                    error_message=f"{self.CMD[0] if self.CMD else 'command'} not found in PATH",
                    exit_code=None,
                    family=invocation_family,
                    model=model,
                )

            if result.returncode != 0:
                return InvocationResult(
                    success=False,
                    error_message=result.stderr[:2000] if result.stderr else "Non-zero exit code",
                    exit_code=result.returncode,
                    family=invocation_family,
                    model=model,
                )

            output_text = result.stdout
            if len(output_text.encode("utf-8")) > MAX_ARTIFACT_SIZE_BYTES:
                return InvocationResult(
                    success=False,
                    error_message=(
                        f"Channel output size ({len(output_text.encode('utf-8'))} bytes) "
                        f"exceeds limit {MAX_ARTIFACT_SIZE_BYTES} bytes"
                    ),
                    exit_code=result.returncode,
                    family=invocation_family,
                    model=model,
                )

            raw_path = outputs_dir / ARTIFACT_FILENAME_RAW_STDOUT
            raw_path.write_text(output_text)

            if not output_text.strip():
                last_stderr = result.stderr or ""
                stderr_path = outputs_dir / ARTIFACT_FILENAME_RAW_STDERR
                stderr_path.write_text(last_stderr)
                if attempt < max_empty_retries:
                    log.warning(
                        "empty_output_retry",
                        channel=self._NAME,
                        attempt=attempt + 1,
                        max_retries=max_empty_retries,
                        delay_s=retry_delay,
                    )
                    time.sleep(retry_delay)
                    continue

                cmd_label = self.CMD[0] if self.CMD else "channel"
                err_parts = [f"Empty output from {cmd_label}"]
                if last_stderr.strip():
                    err_parts.append(f"stderr: {last_stderr[:500]}")
                return InvocationResult(
                    success=False,
                    error_message="; ".join(err_parts),
                    exit_code=result.returncode,
                    family=invocation_family,
                    model=model,
                )

            break

        json_data = extract_json_from_output(output_text)
        if json_data is not None and json_data.get("status") == "cannot_proceed":
            cp_path = outputs_dir / ARTIFACT_FILENAME_CANNOT_PROCEED
            cp_path.write_text(json.dumps(json_data, indent=2))
            return InvocationResult(
                success=False,
                artifact_name=None,
                error_message="cannot_proceed",
                family=invocation_family,
                model=model,
            )

        artifact_content = extract_artifact_from_output(output_text)
        if artifact_content is None:
            return InvocationResult(
                success=False,
                error_message=(
                    "Could not extract artifact from "
                    f"{self.CMD[0] if self.CMD else 'channel'} output"
                ),
                exit_code=result.returncode,
                family=invocation_family,
                model=model,
            )

        ext = self._artifact_extension_for_role(role)
        artifact_name = f"artifact{ext}"
        artifact_path = outputs_dir / artifact_name
        artifact_path.write_text(artifact_content + "\n")
        return InvocationResult(
            success=True,
            artifact_name=artifact_name,
            family=invocation_family,
            model=model,
        )
