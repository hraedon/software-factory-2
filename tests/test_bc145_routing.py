from __future__ import annotations

import json
from pathlib import Path

from factory.gate import GateResult, evaluate_review
from factory.router import _ESCALATABLE_KINDS, DiagnosticKind, route


class TestBC145StructuredFindings:
    def test_structured_findings_produce_review_found_defect(self, tmp_path: Path):
        artifact = tmp_path / "review.json"
        artifact.write_text(
            json.dumps(
                {
                    "passed": False,
                    "findings": [
                        {
                            "ac_id": "AC-01",
                            "kind": "impl",
                            "severity": "block",
                            "body": "extract_chain is a stub returning []",
                        },
                        {
                            "ac_id": "AC-01",
                            "kind": "test",
                            "severity": "block",
                            "body": "No test supplies valid DER data",
                        },
                    ],
                    "rationale": "Stub implementation + missing test coverage",
                }
            )
        )
        result = evaluate_review(artifact)
        assert result.passed is False
        assert result.diagnostic_kind == "review_found_defect"
        assert result.custom_fields.get("findings")
        findings = result.custom_fields["findings"]
        assert len(findings) == 2
        assert findings[0]["kind"] == "impl"
        assert findings[1]["kind"] == "test"
        assert "[block] AC-01 (impl): extract_chain is a stub returning []" in result.diagnostics

    def test_legacy_string_findings_parsed_as_cross_family_review(self, tmp_path: Path):
        artifact = tmp_path / "review.json"
        artifact.write_text(
            json.dumps(
                {
                    "passed": False,
                    "findings": ["Missing error handling"],
                    "rationale": "Needs fixing",
                }
            )
        )
        result = evaluate_review(artifact)
        assert result.passed is False
        assert result.diagnostic_kind == "review_found_defect"
        # Legacy strings are treated as block/impl and still rendered
        assert "Missing error handling" in result.diagnostics[0]

    def test_malformed_empty_json_produces_review_malformed(self, tmp_path: Path):
        artifact = tmp_path / "review.json"
        artifact.write_text("")
        result = evaluate_review(artifact)
        assert result.passed is False
        assert result.diagnostic_kind == "review_malformed"
        assert result.diagnostics == ["Reviewer produced no parseable JSON output"]

    def test_malformed_failed_with_no_findings_no_rationale(self, tmp_path: Path):
        artifact = tmp_path / "review.json"
        artifact.write_text(json.dumps({"passed": False, "findings": [], "rationale": ""}))
        result = evaluate_review(artifact)
        assert result.passed is False
        assert result.diagnostic_kind == "review_malformed"

    def test_passed_true_has_empty_diagnostic_kind(self, tmp_path: Path):
        artifact = tmp_path / "review.json"
        artifact.write_text(json.dumps({"passed": True, "findings": [], "rationale": "All good"}))
        result = evaluate_review(artifact)
        assert result.passed is True
        assert result.diagnostic_kind == ""
        assert result.diagnostics == []


class TestBC145RouterDispatch:
    def test_review_found_defect_routes_to_new_with_feedback_pending(self):
        gate = GateResult(
            passed=False,
            gate_name="cross_family_review",
            diagnostics=["[block] AC-01 (impl): stub"],
            diagnostic_kind="review_found_defect",
            custom_fields={"findings": [{"kind": "impl", "body": "stub"}]},
        )
        result = route("gating", "gate_fail", gate_result=gate)
        assert result.target_state == "new"
        assert result.diagnostic_kind == DiagnosticKind.REVIEW_FOUND_DEFECT
        assert result.custom_fields_update.get("review_feedback_pending") is True

    def test_review_found_defect_not_escalatable(self):
        assert DiagnosticKind.REVIEW_FOUND_DEFECT not in _ESCALATABLE_KINDS

    def test_review_malformed_is_escalatable(self):
        assert DiagnosticKind.REVIEW_MALFORMED in _ESCALATABLE_KINDS

    def test_review_malformed_routes_to_new_without_feedback(self):
        gate = GateResult(
            passed=False,
            gate_name="cross_family_review",
            diagnostics=["No parseable JSON"],
            diagnostic_kind="review_malformed",
        )
        result = route("gating", "gate_fail", gate_result=gate)
        assert result.target_state == "new"
        assert result.diagnostic_kind == DiagnosticKind.REVIEW_MALFORMED
        assert "review_feedback_pending" not in result.custom_fields_update

    def test_review_found_defect_at_threshold_does_not_escalate(self):
        gate = GateResult(
            passed=False,
            gate_name="cross_family_review",
            diagnostics=["stub"],
            diagnostic_kind="review_found_defect",
        )
        result = route(
            "gating",
            "gate_fail",
            gate_result=gate,
            attempt_number=3,
            attempt_threshold=3,
        )
        assert result.target_state == "new"
        assert result.diagnostic_kind == DiagnosticKind.REVIEW_FOUND_DEFECT
        assert result.custom_fields_update.get("review_feedback_pending") is True


class TestBC145ContextInjection:
    def test_format_review_feedback_structured(self):
        from factory.context import _format_review_feedback

        raw = [
            {"ac_id": "AC-01", "kind": "impl", "severity": "block", "body": "stub"},
            {"ac_id": "AC-02", "kind": "test", "severity": "advise", "body": "weak coverage"},
        ]
        formatted = _format_review_feedback(raw)
        assert "[block] AC-01 (impl): stub" in formatted
        assert "[advise] AC-02 (test): weak coverage" in formatted

    def test_format_review_feedback_string(self):
        from factory.context import _format_review_feedback

        formatted = _format_review_feedback("plain text")
        assert formatted == "plain text"

    def test_format_review_feedback_dict(self):
        from factory.context import _format_review_feedback

        formatted = _format_review_feedback({"body": "single"})
        assert "single" in formatted

    def test_format_review_feedback_empty(self):
        from factory.context import _format_review_feedback

        formatted = _format_review_feedback([])
        assert formatted == ""
