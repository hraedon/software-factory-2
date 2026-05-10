from __future__ import annotations

from typing import ClassVar

from factory.config import FactoryConfig
from factory.constants import (
    CHANNEL_OPENCODE,
    FAMILY_BY_PROVIDER,
    FAMILY_OPENCODE,
)
from factory.subprocess_channel import SubprocessChannel


def _derive_family(model: str | None) -> str:
    if not model:
        return FAMILY_OPENCODE
    prefix = model.split("/")[0]
    return FAMILY_BY_PROVIDER.get(prefix, prefix)


class OpenCodeChannel(SubprocessChannel):
    CMD: ClassVar[list[str]] = ["opencode", "run", "--dangerously-skip-permissions"]
    _NAME: ClassVar[str] = CHANNEL_OPENCODE
    _DEFAULT_FAMILY: ClassVar[str] = FAMILY_OPENCODE

    def __init__(self, config: FactoryConfig):
        super().__init__(config)

    def _derive_invocation_family(self, role_config) -> str:
        model = role_config.model if role_config else None
        return _derive_family(model)
