from __future__ import annotations

import uuid

from factory.constants import (
    STATE_IN_PROGRESS,
    STATE_LOCKED,
    STATE_NEW,
    TRANSITION_GATE_FAIL,
    TRANSITION_GATE_PASS,
    TRANSITION_SUBMIT,
)
from factory.telemetry import run_telemetry_verify


class FakeSubstrate:
    def __init__(self):
        self._events: dict[str, list] = {}
        self._work_items: dict = {}

    def add_work_item(self, work_item_id, current_state, work_item_type="interface_spec"):
        self._work_items[str(work_item_id)] = type(
            "WI",
            (),
            {
                "work_item_id": work_item_id,
                "current_state": current_state,
                "work_item_type": work_item_type,
            },
        )()

    def add_event(
        self,
        work_item_id,
        transition,
        actor_metadata=None,
        payload=None,
        custom_fields=None,
    ):
        ev = type(
            "EV",
            (),
            {
                "transition": transition,
                "actor_metadata": actor_metadata or {},
                "payload": payload,
                "custom_fields": custom_fields,
            },
        )()
        self._events.setdefault(str(work_item_id), []).append(ev)

    def query_work_items(self, **kwargs):
        return type("Page", (), {"items": list(self._work_items.values())})()

    def read_events(self, work_item_id, limit=1000):
        return self._events.get(str(work_item_id), [])[:limit]

    def close(self):
        pass


class FakeConfig:
    workflow_name = "test"
    workflow_version = 1
    query_page_size = 50
    telemetry_event_limit = 500
    dsn = ""
    project_name = ""
    hmac_key_path = ""


def test_verify_clean_passes() -> None:
    sub = FakeSubstrate()
    wi = uuid.uuid4()
    sub.add_work_item(wi, STATE_LOCKED)
    sub.add_event(
        wi,
        TRANSITION_SUBMIT,
        actor_metadata={
            "role": "interface_architect",
            "channel": "claude-code",
            "family": "anthropic",
        },
    )
    sub.add_event(wi, TRANSITION_GATE_PASS, actor_metadata={"gate_name": "interface_spec"})

    # Monkey-patch Substrate creation inside run_telemetry_verify
    import factory.telemetry as telemetry_mod

    original_substrate = telemetry_mod.Substrate
    telemetry_mod.Substrate = lambda *a, **k: sub
    try:
        result = run_telemetry_verify(FakeConfig())
    finally:
        telemetry_mod.Substrate = original_substrate

    assert result.passed is True
    assert result.unknown_gate_name_count == 0
    assert result.orphan_submit_count == 0
    assert result.unmatched_gate_count == 0
    assert result.confounding_warning_count == 0


def test_verify_unknown_gate_name_fails() -> None:
    sub = FakeSubstrate()
    wi = uuid.uuid4()
    sub.add_work_item(wi, STATE_LOCKED)
    sub.add_event(
        wi,
        TRANSITION_SUBMIT,
        actor_metadata={
            "role": "interface_architect",
            "channel": "claude-code",
            "family": "anthropic",
        },
    )
    sub.add_event(wi, TRANSITION_GATE_FAIL, actor_metadata={}, payload={"diagnostics": {}})

    import factory.telemetry as telemetry_mod

    original_substrate = telemetry_mod.Substrate
    telemetry_mod.Substrate = lambda *a, **k: sub
    try:
        result = run_telemetry_verify(FakeConfig())
    finally:
        telemetry_mod.Substrate = original_substrate

    assert result.passed is False
    assert result.unknown_gate_name_count == 1


def test_verify_orphan_submit_fails() -> None:
    sub = FakeSubstrate()
    wi = uuid.uuid4()
    sub.add_work_item(wi, STATE_NEW)  # not in_progress
    sub.add_event(
        wi,
        TRANSITION_SUBMIT,
        actor_metadata={
            "role": "interface_architect",
            "channel": "claude-code",
            "family": "anthropic",
        },
    )

    import factory.telemetry as telemetry_mod

    original_substrate = telemetry_mod.Substrate
    telemetry_mod.Substrate = lambda *a, **k: sub
    try:
        result = run_telemetry_verify(FakeConfig())
    finally:
        telemetry_mod.Substrate = original_substrate

    assert result.passed is False
    assert result.orphan_submit_count == 1


def test_verify_in_progress_not_orphan() -> None:
    sub = FakeSubstrate()
    wi = uuid.uuid4()
    sub.add_work_item(wi, STATE_IN_PROGRESS)
    sub.add_event(
        wi,
        TRANSITION_SUBMIT,
        actor_metadata={
            "role": "interface_architect",
            "channel": "claude-code",
            "family": "anthropic",
        },
    )

    import factory.telemetry as telemetry_mod

    original_substrate = telemetry_mod.Substrate
    telemetry_mod.Substrate = lambda *a, **k: sub
    try:
        result = run_telemetry_verify(FakeConfig())
    finally:
        telemetry_mod.Substrate = original_substrate

    assert result.orphan_submit_count == 0
    assert result.passed is True


def test_verify_unmatched_gate_fails() -> None:
    sub = FakeSubstrate()
    wi = uuid.uuid4()
    sub.add_work_item(wi, STATE_LOCKED)
    sub.add_event(wi, TRANSITION_GATE_PASS, actor_metadata={"gate_name": "interface_spec"})

    import factory.telemetry as telemetry_mod

    original_substrate = telemetry_mod.Substrate
    telemetry_mod.Substrate = lambda *a, **k: sub
    try:
        result = run_telemetry_verify(FakeConfig())
    finally:
        telemetry_mod.Substrate = original_substrate

    assert result.passed is False
    assert result.unmatched_gate_count == 1
