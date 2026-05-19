"""BC-194 / RFC-037: channel status declaration is enforced at construction time.

_CHANNEL_STATUS must match the declared status in AGENTS.md. _create_channels
raises ChannelDisabled for disabled channels and warns for unvalidated ones.
"""

from __future__ import annotations

import warnings
from dataclasses import replace

import pytest

from factory.channel import ChannelDisabledError
from factory.config import FactoryConfig, RoleConfig
from factory.constants import CHANNEL_GEMINI_CLI, CHANNEL_OPENCODE, ROLE_INTERFACE_ARCHITECT
from factory.runner import _create_channels


def _config_with_channel(channel: str, tmp_path) -> FactoryConfig:
    base = FactoryConfig.phase2(workspace_root=tmp_path / "work")
    roles = (RoleConfig(role=ROLE_INTERFACE_ARCHITECT, channel=channel),)
    return replace(base, roles=roles)


def test_disabled_channel_raises(tmp_path):
    """A config selecting a disabled channel must raise ChannelDisabled before constructing."""
    config = _config_with_channel(CHANNEL_GEMINI_CLI, tmp_path)
    with pytest.raises(ChannelDisabledError, match="gemini-cli"):
        _create_channels(config)


def test_validated_channel_constructs_without_warning(tmp_path, monkeypatch):
    """A validated channel must not trigger any warning."""
    # Patch the constructor so we don't need credentials wired up.
    from factory.runner import _CHANNEL_CONSTRUCTORS

    class _FakeChannel:
        name = "opencode"
        family = "test"

        def __init__(self, config):
            pass

        def invoke(self, *args, **kwargs):
            raise NotImplementedError

    monkeypatch.setitem(_CHANNEL_CONSTRUCTORS, CHANNEL_OPENCODE, _FakeChannel)

    config = _config_with_channel(CHANNEL_OPENCODE, tmp_path)
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        channels = _create_channels(config)
    assert CHANNEL_OPENCODE in channels
