from __future__ import annotations

import json
from pathlib import Path

from factory.gate import evaluate_jury, evaluate_review


class TestEvaluateReviewRejection:
    def test_reject_with_findings(self, tmp_path):
        artifact = tmp_path / "review.json"
        artifact.write_text(
            json.dumps(
                {
                    "passed": False,
                    "findings": [
                        "parse_int raises ValueError on non-numeric input",
                        "safe_divide uses try/except instead of conditional",
                    ],
                    "rationale": "Two AC violations detected",
                }
            )
        )
        result = evaluate_review(artifact)
        assert result.passed is False
        assert len(result.diagnostics) == 3
        assert "parse_int" in result.diagnostics[0]
        assert "safe_divide" in result.diagnostics[1]
        assert "Rationale" in result.diagnostics[2]

    def test_reject_without_findings(self, tmp_path):
        artifact = tmp_path / "review.json"
        artifact.write_text(
            json.dumps(
                {
                    "passed": False,
                    "findings": [],
                    "rationale": "Implementation does not match interface",
                }
            )
        )
        result = evaluate_review(artifact)
        assert result.passed is False
        assert any("no findings" in d for d in result.diagnostics)

    def test_reject_no_rationale(self, tmp_path):
        artifact = tmp_path / "review.json"
        artifact.write_text(
            json.dumps(
                {
                    "passed": False,
                    "findings": ["Missing error handling"],
                }
            )
        )
        result = evaluate_review(artifact)
        assert result.passed is False
        assert "Missing error handling" in result.diagnostics[0]

    def test_approve(self, tmp_path):
        artifact = tmp_path / "review.json"
        artifact.write_text(
            json.dumps(
                {
                    "passed": True,
                    "findings": [],
                    "rationale": "All ACs satisfied",
                }
            )
        )
        result = evaluate_review(artifact)
        assert result.passed is True
        assert result.diagnostics == []

    def test_malformed_json_treated_as_rejection(self, tmp_path):
        artifact = tmp_path / "review.json"
        artifact.write_text("not json at all")
        result = evaluate_review(artifact)
        assert result.passed is False

    def test_non_boolean_passed_treated_as_rejection(self, tmp_path):
        artifact = tmp_path / "review.json"
        artifact.write_text(
            json.dumps(
                {
                    "passed": "yes",
                    "findings": [],
                }
            )
        )
        result = evaluate_review(artifact)
        assert result.passed is True


class TestEvaluateJuryRejection:
    def test_all_against_with_channel_failures(self, tmp_path):
        artifact = tmp_path / "jury_verdict.json"
        artifact.write_text(
            json.dumps(
                {
                    "passed": False,
                    "quorum_met": False,
                    "votes_for": 0,
                    "votes_against": 2,
                    "disagreement_rationale": (
                        "[all_against] opencode: channel fail; claude-code: channel fail"
                    ),
                }
            )
        )
        result = evaluate_jury(artifact)
        assert result.passed is False
        assert any("All jurors against" in d for d in result.diagnostics)
        assert any("channel fail" in d for d in result.diagnostics)

    def test_all_against_genuine_rejection(self, tmp_path):
        artifact = tmp_path / "jury_verdict.json"
        artifact.write_text(
            json.dumps(
                {
                    "passed": False,
                    "quorum_met": False,
                    "votes_for": 0,
                    "votes_against": 2,
                    "disagreement_rationale": (
                        "[all_against] opencode: Implementation violates AC-01; "
                        "claude-code: Missing edge case handling"
                    ),
                }
            )
        )
        result = evaluate_jury(artifact)
        assert result.passed is False
        assert any("All jurors against" in d for d in result.diagnostics)
        assert any("AC-01" in d for d in result.diagnostics)

    def test_split_disagreement(self, tmp_path):
        artifact = tmp_path / "jury_verdict.json"
        artifact.write_text(
            json.dumps(
                {
                    "passed": False,
                    "quorum_met": False,
                    "votes_for": 1,
                    "votes_against": 2,
                    "disagreement_rationale": (
                        "For: opencode: Looks correct | Against: claude-code: Missing edge cases"
                    ),
                }
            )
        )
        result = evaluate_jury(artifact)
        assert result.passed is False
        assert any("Disagreement" in d for d in result.diagnostics)

    def test_empty_rationale_still_shows_quorum(self, tmp_path):
        artifact = tmp_path / "jury_verdict.json"
        artifact.write_text(
            json.dumps(
                {
                    "passed": False,
                    "quorum_met": False,
                    "votes_for": 0,
                    "votes_against": 2,
                    "disagreement_rationale": "",
                }
            )
        )
        result = evaluate_jury(artifact)
        assert result.passed is False
        assert len(result.diagnostics) == 1
        assert "Jury quorum not met" in result.diagnostics[0]


class TestBrokenImplFixture:
    def test_fixture_exists(self):
        fixture_dir = Path("tests/fixtures/broken-impl")
        assert fixture_dir.is_dir()
        assert (fixture_dir / "wi_broken_calc.md").exists()
        assert (fixture_dir / "requirements.txt").exists()

    def test_fixture_has_acs(self):
        content = (Path("tests/fixtures/broken-impl") / "wi_broken_calc.md").read_text()
        assert "AC-01" in content
        assert "AC-02" in content
        assert "AC-03" in content
