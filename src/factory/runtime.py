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

    @property
    def workspace_root(self) -> Path:
        return Path(self.config.workspace_root)
