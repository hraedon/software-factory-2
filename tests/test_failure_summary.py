from __future__ import annotations

import json

from factory.failure_summary import FailureEntry, failures_to_json


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
                gate_name="interface_spec_syntax",
                diagnostic="SyntaxError: invalid syntax",
            )
        ]
        result = failures_to_json(entries)
        parsed = json.loads(result)
        assert len(parsed) == 1
        assert parsed[0]["attempt_number"] == 1
        assert parsed[0]["gate_name"] == "interface_spec_syntax"

    def test_multiple_failures_ordered(self):
        entries = [
            FailureEntry(
                attempt_number=1,
                role="mechanical_gate",
                channel="code",
                gate_name="syntax",
                diagnostic="bad syntax",
            ),
            FailureEntry(
                attempt_number=2,
                role="mechanical_gate",
                channel="code",
                gate_name="ac_reference",
                diagnostic="missing AC",
            ),
        ]
        result = failures_to_json(entries)
        parsed = json.loads(result)
        assert len(parsed) == 2
        assert parsed[0]["attempt_number"] == 1
        assert parsed[1]["attempt_number"] == 2
