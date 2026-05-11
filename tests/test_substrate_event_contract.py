from __future__ import annotations

from substrate import Event


def test_event_has_no_custom_fields_attribute() -> None:
    assert not hasattr(Event, "custom_fields"), (
        "Event should not have custom_fields attribute. "
        "Substrate merges custom_fields into WorkItem, not per-event. "
        "See BC-071."
    )


def test_event_fields_are_readonly() -> None:
    import dataclasses

    assert dataclasses.is_dataclass(Event)
    field_names = {f.name for f in dataclasses.fields(Event)}
    expected = {
        "event_id",
        "work_item_id",
        "transition",
        "actor_id",
        "timestamp",
        "payload",
        "actor_metadata",
    }
    assert expected <= field_names, f"Missing fields: {expected - field_names}"
