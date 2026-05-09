from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.event_schemas import (
    ChannelFailPayload,
    GateFailPayload,
    GatePassPayload,
)

SAMPLE_PATH = Path(__file__).parent / "fixtures" / "event_replay_sample.json"


def test_event_replay_sample_validates() -> None:
    """Load anonymized event subset and assert every payload parses cleanly.

    This is the regression fixture for event-shape drift. If a producer changes
    its payload shape, this test will fail and force an explicit schema update.
    """
    raw = json.loads(SAMPLE_PATH.read_text())
    for entry in raw:
        transition = entry["transition"]
        payload = entry.get("payload", {})
        if transition == "gate_pass":
            assert GatePassPayload.from_dict(payload) is not None
        elif transition in ("gate_fail", "gate_escalation"):
            assert GateFailPayload.from_dict(payload) is not None
        elif transition == "channel_fail":
            assert ChannelFailPayload.from_dict(payload) is not None
        else:
            pytest.fail(f"Unhandled transition in replay sample: {transition}")


def test_event_replay_unknown_transition_is_covered() -> None:
    """If the sample ever gains a new transition type, this forces a parser branch."""
    raw = json.loads(SAMPLE_PATH.read_text())
    seen = {e["transition"] for e in raw}
    assert seen <= {"gate_pass", "gate_fail", "gate_escalation", "channel_fail"}
