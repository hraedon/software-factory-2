from __future__ import annotations

import json

from factory.constants import (
    GATE_NAME_INTERFACE_SPEC_SYNTAX,
    GATE_NAME_UNKNOWN,
)
from factory.failure_summary import FailureEntry, derive_failures, failures_to_json


class TestFailuresToJson:
    def test_empty_list(self):
        result = failures_to_json([])
        parsed = json.loads(result)
        assert parsed == []

    def test_single_failure(self):
        entries = [
            FailureEntry(
                attempt_number=1,
                role="mechanical_gate",
                channel="code",
                failure_type="gate_fail",
                gate_name=GATE_NAME_INTERFACE_SPEC_SYNTAX,
                diagnostic="SyntaxError: invalid syntax",
            )
        ]
        result = failures_to_json(entries)
        parsed = json.loads(result)
        assert len(parsed) == 1
        assert parsed[0]["attempt_number"] == 1
        assert parsed[0]["gate_name"] == GATE_NAME_INTERFACE_SPEC_SYNTAX
        assert parsed[0]["failure_type"] == "gate_fail"

    def test_multiple_failures_ordered(self):
        entries = [
            FailureEntry(
                attempt_number=1,
                role="mechanical_gate",
                channel="code",
                failure_type="gate_fail",
                gate_name="syntax",
                diagnostic="bad syntax",
            ),
            FailureEntry(
                attempt_number=2,
                role="mechanical_gate",
                channel="code",
                failure_type="gate_fail",
                gate_name="ac_reference",
                diagnostic="missing AC",
            ),
        ]
        result = failures_to_json(entries)
        parsed = json.loads(result)
        assert len(parsed) == 2
        assert parsed[0]["attempt_number"] == 1
        assert parsed[1]["attempt_number"] == 2

    def test_channel_fail_entry(self):
        entries = [
            FailureEntry(
                attempt_number=1,
                role="interface_architect",
                channel="claude-code",
                failure_type="channel_fail",
                error_message="timeout",
                timed_out=True,
                exit_code=-1,
            )
        ]
        result = failures_to_json(entries)
        parsed = json.loads(result)
        assert parsed[0]["failure_type"] == "channel_fail"
        assert parsed[0]["error_message"] == "timeout"
        assert parsed[0]["timed_out"] is True
        assert parsed[0]["exit_code"] == -1

    def test_mixed_failure_types(self):
        entries = [
            FailureEntry(
                attempt_number=1,
                role="interface_architect",
                channel="claude-code",
                failure_type="channel_fail",
                error_message="timeout",
                timed_out=True,
            ),
            FailureEntry(
                attempt_number=2,
                role="mechanical_gate",
                channel="code",
                failure_type="gate_fail",
                gate_name="syntax",
                diagnostic="bad",
            ),
        ]
        result = failures_to_json(entries)
        parsed = json.loads(result)
        assert parsed[0]["failure_type"] == "channel_fail"
        assert parsed[1]["failure_type"] == "gate_fail"


class TestDeriveFailures:
    def test_no_failures_returns_empty(self, mock_substrate):
        wi, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test",
            custom_fields={"spec_section": "x", "ac_ids": ["AC-01"]},
        )
        result = derive_failures(mock_substrate, wi.work_item_id)
        assert result == []

    def test_single_gate_fail(self, mock_substrate):
        wi, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test",
            custom_fields={"spec_section": "x", "ac_ids": ["AC-01"]},
        )
        mock_substrate.transition(
            wi.work_item_id,
            "claim",
            "test-worker",
            actor_metadata={"role": "interface_architect"},
        )
        mock_substrate.transition(
            wi.work_item_id,
            "submit",
            "test-worker",
            actor_metadata={"role": "interface_architect"},
        )
        mock_substrate.transition(
            wi.work_item_id,
            "gate_fail",
            "test-gate",
            actor_metadata={
                "role": "mechanical_gate",
                "channel": "code",
                "gate_name": "interface_spec_syntax",
                "attempt_n": 1,
            },
            payload={
                "diagnostics": {
                    "gate_name": "interface_spec_syntax",
                    "passed": False,
                    "messages": ["SyntaxError at line 5"],
                    "message": "SyntaxError at line 5",
                }
            },
        )
        failures = derive_failures(mock_substrate, wi.work_item_id)
        assert len(failures) == 1
        assert failures[0].attempt_number == 1
        assert failures[0].role == "mechanical_gate"
        assert failures[0].channel == "code"
        assert failures[0].failure_type == "gate_fail"
        assert failures[0].gate_name == GATE_NAME_INTERFACE_SPEC_SYNTAX
        assert failures[0].diagnostic == "SyntaxError at line 5"

    def test_single_channel_fail(self, mock_substrate):
        wi, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test",
            custom_fields={"spec_section": "x", "ac_ids": ["AC-01"]},
        )
        mock_substrate.transition(
            wi.work_item_id,
            "claim",
            "test-worker",
            actor_metadata={"role": "interface_architect"},
        )
        mock_substrate.transition(
            wi.work_item_id,
            "channel_fail",
            "test-worker",
            actor_metadata={
                "role": "interface_architect",
                "channel": "claude-code",
                "attempt_n": 1,
            },
            payload={
                "diagnostics": {
                    "error_message": "timeout",
                    "timed_out": True,
                    "exit_code": -1,
                }
            },
        )
        failures = derive_failures(mock_substrate, wi.work_item_id)
        assert len(failures) == 1
        assert failures[0].attempt_number == 1
        assert failures[0].role == "interface_architect"
        assert failures[0].channel == "claude-code"
        assert failures[0].failure_type == "channel_fail"
        assert failures[0].error_message == "timeout"
        assert failures[0].timed_out is True
        assert failures[0].exit_code == -1

    def test_mixed_gate_and_channel_fails(self, mock_substrate):
        wi, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test",
            custom_fields={"spec_section": "x", "ac_ids": ["AC-01"]},
        )
        mock_substrate.transition(
            wi.work_item_id,
            "claim",
            "test-worker",
            actor_metadata={"role": "interface_architect"},
        )
        mock_substrate.transition(
            wi.work_item_id,
            "channel_fail",
            "test-worker",
            actor_metadata={
                "role": "interface_architect",
                "channel": "claude-code",
                "attempt_n": 1,
            },
            payload={
                "diagnostics": {
                    "error_message": "timeout",
                    "timed_out": True,
                    "exit_code": -1,
                }
            },
        )
        mock_substrate.transition(
            wi.work_item_id,
            "claim",
            "test-worker2",
            actor_metadata={"role": "interface_architect"},
        )
        mock_substrate.transition(
            wi.work_item_id,
            "submit",
            "test-worker2",
            actor_metadata={"role": "interface_architect"},
        )
        mock_substrate.transition(
            wi.work_item_id,
            "gate_fail",
            "test-gate",
            actor_metadata={
                "role": "mechanical_gate",
                "channel": "code",
                "gate_name": "interface_spec_syntax",
                "attempt_n": 2,
            },
            payload={
                "diagnostics": {
                    "gate_name": "interface_spec_syntax",
                    "passed": False,
                    "messages": ["bad"],
                    "message": "bad",
                }
            },
        )
        failures = derive_failures(mock_substrate, wi.work_item_id)
        assert len(failures) == 2
        assert failures[0].failure_type == "channel_fail"
        assert failures[0].attempt_number == 1
        assert failures[1].failure_type == "gate_fail"
        assert failures[1].attempt_number == 2

    def test_multiple_gate_fails(self, mock_substrate):
        wi, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test",
            custom_fields={"spec_section": "x", "ac_ids": ["AC-01"]},
        )
        mock_substrate.transition(
            wi.work_item_id,
            "claim",
            "test-worker",
            actor_metadata={"role": "interface_architect"},
        )
        mock_substrate.transition(
            wi.work_item_id,
            "submit",
            "test-worker",
            actor_metadata={"role": "interface_architect"},
        )
        mock_substrate.transition(
            wi.work_item_id,
            "gate_fail",
            "test-gate",
            actor_metadata={
                "role": "mechanical_gate",
                "channel": "code",
                "gate_name": "syntax",
                "attempt_n": 1,
            },
            payload={
                "diagnostics": {
                    "gate_name": "syntax",
                    "passed": False,
                    "messages": ["bad"],
                    "message": "bad",
                }
            },
        )
        mock_substrate.transition(
            wi.work_item_id,
            "claim",
            "test-worker",
            actor_metadata={"role": "interface_architect"},
        )
        mock_substrate.transition(
            wi.work_item_id,
            "submit",
            "test-worker",
            actor_metadata={"role": "interface_architect"},
        )
        mock_substrate.transition(
            wi.work_item_id,
            "gate_fail",
            "test-gate",
            actor_metadata={
                "role": "mechanical_gate",
                "channel": "code",
                "gate_name": "ac_reference",
                "attempt_n": 2,
            },
            payload={
                "diagnostics": {
                    "gate_name": "ac_reference",
                    "passed": False,
                    "messages": ["missing AC-02"],
                    "message": "missing AC-02",
                }
            },
        )
        failures = derive_failures(mock_substrate, wi.work_item_id)
        assert len(failures) == 2
        assert failures[0].attempt_number == 1
        assert failures[0].gate_name == "syntax"
        assert failures[1].attempt_number == 2
        assert failures[1].gate_name == "ac_reference"

    def test_non_failure_events_ignored(self, mock_substrate):
        wi, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test",
            custom_fields={"spec_section": "x", "ac_ids": ["AC-01"]},
        )
        mock_substrate.transition(
            wi.work_item_id,
            "claim",
            "test-worker",
            actor_metadata={"role": "interface_architect"},
        )
        mock_substrate.transition(
            wi.work_item_id,
            "submit",
            "test-worker",
            actor_metadata={"role": "interface_architect"},
        )
        mock_substrate.transition(
            wi.work_item_id,
            "gate_fail",
            "test-gate",
            actor_metadata={
                "role": "mechanical_gate",
                "channel": "code",
                "gate_name": "syntax",
                "attempt_n": 1,
            },
            payload={
                "diagnostics": {
                    "gate_name": "syntax",
                    "passed": False,
                    "messages": ["bad"],
                    "message": "bad",
                }
            },
        )
        failures = derive_failures(mock_substrate, wi.work_item_id)
        assert len(failures) == 1

    def test_missing_diagnostics_defaults(self, mock_substrate):
        wi, _ = mock_substrate.create_work_item(
            workflow_name="software_factory",
            work_item_type="interface_spec",
            actor_id="test",
            custom_fields={"spec_section": "x", "ac_ids": ["AC-01"]},
        )
        mock_substrate.transition(
            wi.work_item_id,
            "claim",
            "test-worker",
            actor_metadata={"role": "interface_architect"},
        )
        mock_substrate.transition(
            wi.work_item_id,
            "submit",
            "test-worker",
            actor_metadata={"role": "interface_architect"},
        )
        mock_substrate.transition(
            wi.work_item_id,
            "gate_fail",
            "test-gate",
            actor_metadata={"role": "mechanical_gate", "channel": "code", "attempt_n": 1},
        )
        failures = derive_failures(mock_substrate, wi.work_item_id)
        assert len(failures) == 1
        assert failures[0].gate_name == GATE_NAME_UNKNOWN
        assert failures[0].diagnostic == ""
