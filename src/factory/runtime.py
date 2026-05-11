from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from substrate import Substrate

from factory.config import FactoryConfig

if TYPE_CHECKING:
    from factory.channel import Channel


@dataclass(frozen=True)
class PipelineRuntime:
    sub: Substrate
    config: FactoryConfig
    spec_content: str | None = None
    channel: Channel | None = None
    channels: dict[str, Channel] | None = None

    @property
    def workspace_root(self) -> Path:
        return Path(self.config.workspace_root)

    def channel_for_role(self, role: str) -> Channel:
        role_config = self.config.get_role_config(role)
        channel_name = role_config.channel if role_config else None
        if self.channels and channel_name and channel_name in self.channels:
            return self.channels[channel_name]
        if self.channel is not None:
            return self.channel
        raise ValueError(f"No channel available for role {role}")
