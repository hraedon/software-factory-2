from __future__ import annotations

import os
from pathlib import Path
from typing import ClassVar

from factory.config import FactoryConfig
from factory.constants import (
    CHANNEL_GEMINI_CLI,
    FAMILY_GEMINI,
)
from factory.subprocess_channel import SubprocessChannel

_DEFAULT_NODE_BIN = Path.home() / ".nvm" / "versions" / "node" / "v24.15.0" / "bin"


class GeminiCLIChannel(SubprocessChannel):
    CMD: ClassVar[list[str]] = ["gemini", "-p", "-", "--yolo", "--skip-trust"]
    _NAME: ClassVar[str] = CHANNEL_GEMINI_CLI
    _DEFAULT_FAMILY: ClassVar[str] = FAMILY_GEMINI

    def __init__(self, config: FactoryConfig):
        super().__init__(config)

    def _build_cmd(self, role_config) -> list[str]:
        cmd = list(self.CMD)
        model = role_config.model if role_config else None
        if model:
            cmd.extend(["-m", model])
        return cmd

    def _derive_invocation_family(self, role_config) -> str:
        return FAMILY_GEMINI

    def _extra_env(self) -> dict[str, str] | None:
        node_bin = self._config.gemini_node_bin or _DEFAULT_NODE_BIN
        if node_bin.is_dir():
            current_path = os.environ.get("PATH", "")
            bin_str = str(node_bin)
            if bin_str not in current_path:
                return {"PATH": f"{bin_str}:{current_path}"}
        return None

    def invoke(
        self,
        role,
        prompt,
        outputs_dir,
        timeout,
        extra_env=None,
        model_override=None,
        cancel_event=None,
    ):
        merged_env = extra_env or {}
        node_env = self._extra_env()
        if node_env:
            merged_env = {**merged_env, **node_env}
        return super().invoke(
            role,
            prompt,
            outputs_dir,
            timeout,
            extra_env=merged_env or None,
            model_override=model_override,
            cancel_event=cancel_event,
        )
