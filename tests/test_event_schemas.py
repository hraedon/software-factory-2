from __future__ import annotations

import pytest

from factory.event_schemas import (
    ChannelFailPayload,
    EventSchemaError,
    GateFailPayload,
    GatePassPayload,
    SubmitPayload,
)


class TestRoundTrips:
    def test_submit_payload_round_trip(self) -> None:
        original = SubmitPayload()
        d = original.to_dict()
        restored = SubmitPayload.from_dict(d)
        assert original == restored

    def test_gate_pass_payload_round_trip(self) -> None:
        original = GatePassPayload()
        d = original.to_dict()
        restored = GatePassPayload.from_dict(d)
        assert original == restored

    def test_gate_fail_payload_round_trip(self) -> None:
        original = GateFailPayload(diagnostics={"gate_name": "impl_lint", "message": "bad"})
        d = original.to_dict()
        restored = GateFailPayload.from_dict(d)
        assert original == restored

    def test_channel_fail_payload_round_trip(self) -> None:
        original = ChannelFailPayload(
            diagnostics={"error_message": "timeout", "timed_out": True, "exit_code": 1}
        )
        d = original.to_dict()
        restored = ChannelFailPayload.from_dict(d)
        assert original == restored


class TestValidation:
    def test_gate_fail_missing_diagnostics_raises(self) -> None:
        with pytest.raises(EventSchemaError, match="missing required field 'diagnostics'"):
            GateFailPayload.from_dict({})

    def test_gate_fail_non_dict_diagnostics_raises(self) -> None:
        with pytest.raises(EventSchemaError, match="'diagnostics' must be a dict"):
            GateFailPayload.from_dict({"diagnostics": "not-a-dict"})

    def test_channel_fail_missing_diagnostics_raises(self) -> None:
        with pytest.raises(EventSchemaError, match="missing required field 'diagnostics'"):
            ChannelFailPayload.from_dict({})

    def test_non_dict_input_raises(self) -> None:
        with pytest.raises(EventSchemaError, match="must be a dict"):
            GateFailPayload.from_dict("bad")


class TestUnknownFieldWarning:
    def test_gate_fail_warns_on_unknown_fields(self, caplog) -> None:
        import logging

        with caplog.at_level(logging.WARNING, logger="factory.event_schemas"):
            GateFailPayload.from_dict({"diagnostics": {"gate_name": "g"}, "extra_field": 123})
        assert "event_schema_unknown_fields" in caplog.text
        assert "extra_field" in caplog.text


class TestFromDictFallback:
    def test_gate_fail_from_empty_dict_fails(self) -> None:
        with pytest.raises(EventSchemaError):
            GateFailPayload.from_dict({})

    def test_channel_fail_from_partial_dict_fails(self) -> None:
        with pytest.raises(EventSchemaError):
            ChannelFailPayload.from_dict({"error_message": "x"})
