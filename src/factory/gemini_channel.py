from __future__ import annotations

from typing import ClassVar

from factory.config import FactoryConfig
from factory.constants import (
    CHANNEL_GEMINI_CLI,
    FAMILY_GEMINI,
)
from factory.subprocess_channel import SubprocessChannel


class GeminiCLIChannel(SubprocessChannel):
    CMD: ClassVar[list[str]] = ["gemini"]
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
