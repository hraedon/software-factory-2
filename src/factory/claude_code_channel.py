from __future__ import annotations

from typing import ClassVar

from factory.config import FactoryConfig
from factory.constants import (
    CHANNEL_CLAUDE_CODE,
    FAMILY_ANTHROPIC,
)
from factory.output_extraction import extract_artifact_from_output, extract_json_from_output
from factory.subprocess_channel import SubprocessChannel

_extract_artifact_from_output = extract_artifact_from_output
_extract_json_from_output = extract_json_from_output


class ClaudeCodeChannel(SubprocessChannel):
    CMD: ClassVar[list[str]] = ["claude", "--print", "--output-format", "text", "--max-turns", "1"]
    _NAME: ClassVar[str] = CHANNEL_CLAUDE_CODE
    _DEFAULT_FAMILY: ClassVar[str] = FAMILY_ANTHROPIC

    def __init__(self, config: FactoryConfig):
        super().__init__(config)

    def _derive_invocation_family(self, role_config) -> str:
        return FAMILY_ANTHROPIC
