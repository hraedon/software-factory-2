from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.channel import InvocationResult
from factory.jury import JurorVote, JuryVerdict, _parse_vote, run_jury


class _FakeChannel:
    def __init__(self, name: str, passed: bool, rationale: str = "", success: bool = True):
        self.name = name
        self.family = "test"
        self._passed = passed
        self._rationale = rationale
        self._success = success

    def invoke(self, role, prompt, outputs_dir, timeout, extra_env=None):
        result_path = Path(outputs_dir) / "jury_vote.json"
        result_path.write_text(
            json.dumps(
                {
                    "passed": self._passed,
                    "rationale": self._rationale,
                }
            )
        )
        if not self._success:
            return InvocationResult(success=False, error_message="channel fail")
        return InvocationResult(success=True, artifact_name="jury_vote.json")


class _ExplodingChannel:
    def __init__(self, name: str):
        self.name = name
        self.family = "test"

    def invoke(self, role, prompt, outputs_dir, timeout, extra_env=None):
        raise RuntimeError("boom")


class TestParseVote:
    def test_empty(self):
        assert _parse_vote("") == {}

    def test_valid(self):
        assert _parse_vote('{"passed": true}') == {"passed": True}

    def test_nested_in_text(self):
        text = 'Something\\n```json\\n{"passed": false, "rationale": "no"}\\n```'
        result = _parse_vote(text)
        assert result["passed"] is False


class TestRunJury:
    def test_quorum_met_2_of_3(self, tmp_path):
        channels = {
            "a": _FakeChannel("a", True, "yes"),
            "b": _FakeChannel("b", True, "yes"),
            "c": _FakeChannel("c", False, "no"),
        }
        verdict = run_jury(channels, "prompt", tmp_path, 60, quorum=2)
        assert verdict.passed is True
        assert verdict.votes_for == 2
        assert verdict.votes_against == 1
        assert verdict.quorum_met is True
        assert len(verdict.verdicts) == 3

    def test_quorum_not_met(self, tmp_path):
        channels = {
            "a": _FakeChannel("a", True, "yes"),
            "b": _FakeChannel("b", False, "no"),
            "c": _FakeChannel("c", False, "no"),
        }
        verdict = run_jury(channels, "prompt", tmp_path, 60, quorum=2)
        assert verdict.passed is False
        assert verdict.votes_for == 1
        assert verdict.votes_against == 2
        assert verdict.quorum_met is False
        assert "For:" in verdict.disagreement_rationale
        assert "Against:" in verdict.disagreement_rationale

    def test_unanimous_against(self, tmp_path):
        channels = {
            "a": _FakeChannel("a", False, "no"),
            "b": _FakeChannel("b", False, "no"),
        }
        verdict = run_jury(channels, "prompt", tmp_path, 60, quorum=2)
        assert verdict.passed is False
        assert verdict.disagreement_rationale == ""

    def test_channel_failure(self, tmp_path):
        channels = {
            "a": _FakeChannel("a", True, "yes", success=False),
            "b": _FakeChannel("b", True, "yes"),
        }
        verdict = run_jury(channels, "prompt", tmp_path, 60, quorum=2)
        assert verdict.passed is False
        assert verdict.votes_for == 1
        assert any(v.channel == "a" and not v.passed for v in verdict.verdicts)
        assert any(v.channel == "b" and v.passed for v in verdict.verdicts)

    def test_output_dir_per_channel(self, tmp_path):
        channels = {"a": _FakeChannel("a", True)}
        run_jury(channels, "prompt", tmp_path, 60, quorum=1)
        assert (tmp_path / "a" / "jury_vote.json").exists()

    def test_parallel_invocation_preserves_all_votes(self, tmp_path):
        channels = {
            "a": _FakeChannel("a", True, "yes"),
            "b": _FakeChannel("b", True, "yes"),
            "c": _FakeChannel("c", False, "no"),
        }
        verdict = run_jury(channels, "prompt", tmp_path, 60, quorum=2)
        assert len(verdict.verdicts) == 3
        passed_channels = {v.channel for v in verdict.verdicts if v.passed}
        assert passed_channels == {"a", "b"}

    def test_juror_exception_caught(self, tmp_path):
        channels = {
            "a": _ExplodingChannel("a"),
            "b": _FakeChannel("b", True, "ok"),
        }
        verdict = run_jury(channels, "prompt", tmp_path, 60, quorum=1)
        assert len(verdict.verdicts) == 2
        failed = [v for v in verdict.verdicts if not v.passed]
        assert len(failed) == 1
        assert failed[0].channel == "a"
        assert failed[0].rationale == "juror invocation raised an exception"


class TestJuryVerdictFrozen:
    def test_frozen(self):
        v = JuryVerdict(passed=True, votes_for=2, votes_against=0, quorum_met=True, verdicts=())
        with pytest.raises(AttributeError):
            v.passed = False


class TestJurorVoteFrozen:
    def test_frozen(self):
        vote = JurorVote(passed=True, rationale="ok", channel="x", family="test")
        with pytest.raises(AttributeError):
            vote.passed = False
