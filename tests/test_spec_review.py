"""Tests for :mod:`factory.spec_review`.

No real model invocation — uses FakeChannel to return structured JSON.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.spec_review import (
    SpecReviewFinding,
    SpecReviewResult,
    _build_review_prompt,
    _finding_from_dict,
    _parse_review_json,
    format_review_output,
    load_spec_for_review,
    review_spec,
)


class FakeChannel:
    def __init__(self, response: str = "[]", fail: bool = False):
        self._response = response
        self._fail = fail
        self.name = "test"
        self.family = "test-family"

    def invoke(self, role, prompt, outputs_dir, timeout, **kwargs):
        if self._fail:
            from factory.channel import InvocationResult

            return InvocationResult(
                success=False,
                error_message="test failure",
                exit_code=1,
            )
        out = Path(outputs_dir) / "artifact.json"
        out.write_text(self._response)
        from factory.channel import InvocationResult

        return InvocationResult(success=True, artifact_name="artifact.json")


SAMPLE_FINDINGS = [
    {
        "pattern": "orphaned_definition",
        "module": "scheduler",
        "symbol": "start_scheduler()",
        "detail": "No AC places this in the runtime lifecycle.",
        "inferred_answer": "Called at app startup via framework lifespan hook.",
        "confidence": 0.88,
        "severity": "high",
    },
    {
        "pattern": "missing_runtime_context",
        "module": "alerts",
        "symbol": "AlertConfig",
        "detail": "SMTP fields with no stated source.",
        "inferred_answer": "Environment variables.",
        "confidence": 0.92,
        "severity": "high",
    },
    {
        "pattern": "write_only_data_path",
        "module": "scan",
        "symbol": "scan_history",
        "detail": "Written by scheduler, no consumer.",
        "inferred_answer": None,
        "confidence": 0.2,
        "severity": "medium",
    },
]


class TestParseReviewJson:
    def test_fenced_json_array(self):
        raw = '```json\n[{"pattern": "test"}]\n```'
        result = _parse_review_json(raw)
        assert len(result) == 1
        assert result[0]["pattern"] == "test"

    def test_fenced_json_object_with_findings(self):
        raw = '```json\n{"findings": [{"pattern": "test"}]}\n```'
        result = _parse_review_json(raw)
        assert len(result) == 1

    def test_plain_json_array(self):
        raw = json.dumps([{"pattern": "test"}])
        result = _parse_review_json(raw)
        assert len(result) == 1

    def test_prefixed_text(self):
        raw = 'Some preamble\n```json\n[{"pattern": "a"}]\n```\nMore text'
        result = _parse_review_json(raw)
        assert len(result) == 1

    def test_empty_array(self):
        assert _parse_review_json("[]") == []

    def test_invalid_json_returns_empty(self):
        assert _parse_review_json("not json at all") == []

    def test_empty_string_returns_empty(self):
        assert _parse_review_json("") == []


class TestFindingFromDict:
    def test_full_dict(self):
        d = SAMPLE_FINDINGS[0]
        f = _finding_from_dict(d)
        assert f.pattern == "orphaned_definition"
        assert f.module == "scheduler"
        assert f.symbol == "start_scheduler()"
        assert f.confidence == 0.88
        assert f.severity == "high"
        assert f.inferred_answer == "Called at app startup via framework lifespan hook."

    def test_minimal_dict(self):
        f = _finding_from_dict({"pattern": "test"})
        assert f.pattern == "test"
        assert f.module == "unknown"
        assert f.confidence == 0.0
        assert f.inferred_answer is None

    def test_none_confidence_defaults_to_zero(self):
        f = _finding_from_dict({"pattern": "test", "confidence": None})
        assert f.confidence == 0.0


class TestSpecReviewFinding:
    def test_auto_resolved_high_confidence(self):
        f = SpecReviewFinding(
            pattern="test", module="m", symbol="s", detail="d",
            inferred_answer="answer", confidence=0.9,
        )
        assert f.is_auto_resolved is True

    def test_not_auto_resolved_low_confidence(self):
        f = SpecReviewFinding(
            pattern="test", module="m", symbol="s", detail="d",
            inferred_answer="answer", confidence=0.3,
        )
        assert f.is_auto_resolved is False

    def test_not_auto_resolved_no_inference(self):
        f = SpecReviewFinding(
            pattern="test", module="m", symbol="s", detail="d",
            inferred_answer=None, confidence=0.9,
        )
        assert f.is_auto_resolved is False


class TestSpecReviewResult:
    def test_passed_when_no_findings(self):
        r = SpecReviewResult(findings=[])
        assert r.passed is True

    def test_passed_when_all_auto_resolved(self):
        findings = [
            SpecReviewFinding(
                pattern="test", module="m", symbol="s", detail="d",
                inferred_answer="a", confidence=0.9,
            ),
        ]
        r = SpecReviewResult(findings=findings, confidence_threshold=0.7)
        assert r.passed is True
        assert len(r.auto_resolved_findings) == 1
        assert len(r.surfaced_findings) == 0

    def test_not_passed_when_surfaced(self):
        findings = [
            SpecReviewFinding(
                pattern="test", module="m", symbol="s", detail="d",
                inferred_answer=None, confidence=0.2,
            ),
        ]
        r = SpecReviewResult(findings=findings, confidence_threshold=0.7)
        assert r.passed is False
        assert len(r.surfaced_findings) == 1

    def test_mixed_findings(self):
        findings = [
            SpecReviewFinding(
                pattern="a", module="m", symbol="s", detail="d",
                inferred_answer="x", confidence=0.9,
            ),
            SpecReviewFinding(
                pattern="b", module="m", symbol="s", detail="d",
                inferred_answer=None, confidence=0.2,
            ),
        ]
        r = SpecReviewResult(findings=findings, confidence_threshold=0.7)
        assert r.passed is False
        assert len(r.auto_resolved_findings) == 1
        assert len(r.surfaced_findings) == 1

    def test_summary_no_findings(self):
        r = SpecReviewResult(findings=[])
        assert "no composition gaps" in r.summary()

    def test_summary_mixed(self):
        findings = [
            SpecReviewFinding(
                pattern="a", module="m", symbol="s", detail="d",
                inferred_answer="x", confidence=0.9,
            ),
            SpecReviewFinding(
                pattern="b", module="m", symbol="s", detail="d",
                inferred_answer=None, confidence=0.2,
            ),
        ]
        r = SpecReviewResult(findings=findings, confidence_threshold=0.7)
        s = r.summary()
        assert "2 findings" in s
        assert "1 auto-resolved" in s
        assert "1 surfaced" in s


class TestBuildReviewPrompt:
    def test_includes_spec_text(self, tmp_path):
        spec = tmp_path / "spec.md"
        spec.write_text("# Test Spec\n\nFR-01: Do stuff.")
        prompt = _build_review_prompt(spec.read_text())
        assert "Do stuff" in prompt
        assert "orphaned_definition" in prompt


class TestLoadSpecForReview:
    def test_load_markdown(self, tmp_path):
        spec = tmp_path / "spec.md"
        spec.write_text("# Test\n\nFR-01: Hello.")
        text = load_spec_for_review(spec)
        assert "Hello" in text

    def test_load_yaml(self, tmp_path):
        spec = tmp_path / "spec.yaml"
        spec.write_text("functional_requirements:\n  - id: FR-01\n    text: Hello.")
        text = load_spec_for_review(spec)
        assert "FR-01" in text

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_spec_for_review(Path("/nonexistent/spec.md"))


class TestReviewSpec:
    def test_clean_spec(self, tmp_path):
        spec = tmp_path / "spec.md"
        spec.write_text("# Test\n\nFR-01: Hello.\n\n## AC-01\nIt works.")
        channel = FakeChannel(response="[]")
        from factory.config import FactoryConfig

        config = FactoryConfig()
        result = review_spec(channel, config, spec)
        assert result.passed is True
        assert len(result.findings) == 0

    def test_spec_with_gaps(self, tmp_path):
        spec = tmp_path / "spec.md"
        spec.write_text("# Test\n\nFR-01: Hello.")
        channel = FakeChannel(response=json.dumps(SAMPLE_FINDINGS))
        from factory.config import FactoryConfig

        config = FactoryConfig()
        result = review_spec(channel, config, spec, confidence_threshold=0.7)
        assert result.passed is False
        assert len(result.findings) == 3
        assert len(result.auto_resolved_findings) == 2
        assert len(result.surfaced_findings) == 1

    def test_channel_failure_returns_empty(self, tmp_path):
        spec = tmp_path / "spec.md"
        spec.write_text("# Test")
        channel = FakeChannel(fail=True)
        from factory.config import FactoryConfig

        config = FactoryConfig()
        result = review_spec(channel, config, spec)
        assert result.passed is True
        assert len(result.findings) == 0

    def test_custom_threshold(self, tmp_path):
        spec = tmp_path / "spec.md"
        spec.write_text("# Test")
        channel = FakeChannel(response=json.dumps(SAMPLE_FINDINGS))
        from factory.config import FactoryConfig

        config = FactoryConfig()
        result = review_spec(channel, config, spec, confidence_threshold=0.95)
        # Only the 0.92 finding passes the 0.95 threshold
        assert len(result.auto_resolved_findings) == 0
        assert len(result.surfaced_findings) == 3


class TestFormatReviewOutput:
    def test_no_findings(self):
        r = SpecReviewResult(findings=[])
        output = format_review_output(r)
        assert "no composition gaps" in output

    def test_with_findings(self):
        findings = [
            SpecReviewFinding(
                pattern="orphaned_definition", module="scheduler",
                symbol="start_scheduler()", detail="No lifecycle AC.",
                inferred_answer="Called at startup.", confidence=0.2,
            ),
            SpecReviewFinding(
                pattern="missing_runtime_context", module="alerts",
                symbol="AlertConfig", detail="No config source.",
                inferred_answer="Env vars.", confidence=0.9,
            ),
        ]
        r = SpecReviewResult(findings=findings, confidence_threshold=0.7)
        output = format_review_output(r)
        assert "SURFACED" in output
        assert "AUTO-RESOLVED" in output
        assert "scheduler" in output
        assert "alerts" in output
