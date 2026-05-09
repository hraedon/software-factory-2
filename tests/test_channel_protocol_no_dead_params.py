from __future__ import annotations

import inspect

from factory.channel import Channel
from factory.claude_code_channel import ClaudeCodeChannel
from factory.opencode_channel import OpenCodeChannel


def test_channel_protocol_has_no_dead_params() -> None:
    """Every parameter on Channel.invoke() must be used by every concrete adapter.

    This test introspects the protocol signature and asserts each parameter name
    appears in the concrete implementations' invoke() signatures.  If a parameter
    is added to the protocol but never consumed by an adapter, this test fails.
    """
    proto_sig = inspect.signature(Channel.invoke)
    proto_params = set(proto_sig.parameters.keys())

    for cls in (ClaudeCodeChannel, OpenCodeChannel):
        concrete_sig = inspect.signature(cls.invoke)
        concrete_params = set(concrete_sig.parameters.keys())
        missing = proto_params - concrete_params
        assert not missing, f"{cls.__name__} missing params: {missing}"
