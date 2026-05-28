from __future__ import annotations

from factory.failure_summarizer import (
    FailureSummary,
    summarize_failures,
)
from factory.failure_summary import FailureEntry


def _make_failure(
    attempt: int,
    role: str = "implementer",
    gate: str = "implementation_mypy",
    diagnostic: str = "",
    error_message: str = "",
) -> FailureEntry:
    return FailureEntry(
        attempt_number=attempt,
        role=role,
        channel="opencode",
        gate_name=gate,
        diagnostic=diagnostic,
        error_message=error_message,
    )


class TestSummarizeFailures:
    def test_returns_none_for_single_failure(self):
        failures = [_make_failure(1, diagnostic="mypy error")]
        assert summarize_failures(failures) is None

    def test_returns_none_for_empty(self):
        assert summarize_failures([]) is None

    def test_returns_summary_for_two_failures(self):
        failures = [
            _make_failure(1, diagnostic="error: incompatible types"),
            _make_failure(2, diagnostic="error: NameError 'foo' not defined"),
        ]
        result = summarize_failures(failures)
        assert result is not None
        assert len(result.constraints) >= 1
        assert isinstance(result.raw_text, str)

    def test_constraints_from_import_refs(self):
        failures = [
            _make_failure(1, diagnostic="error: import certificate_model failed"),
            _make_failure(
                2,
                diagnostic="error: from certificate_model import Certificate failed",
            ),
        ]
        result = summarize_failures(failures)
        assert result is not None
        assert any("certificate_model" in c for c in result.constraints)

    def test_constraints_from_type_mismatches(self):
        failures = [
            _make_failure(1, diagnostic="error: cannot assign `str` to `int`"),
            _make_failure(
                2,
                diagnostic="error: Argument 1 has incompatible type `dict`",
            ),
        ]
        result = summarize_failures(failures)
        assert result is not None

    def test_max_entries_limit(self):
        failures = [_make_failure(i, diagnostic=f"error {i}") for i in range(1, 20)]
        result = summarize_failures(failures, max_entries=5)
        assert result is not None
        assert len(result.raw_text.split("\n")) <= 5

    def test_constraints_capped_at_five(self):
        long_diag = "import a; import b; import c; import d; import e; import f"
        failures = [_make_failure(1, diagnostic=long_diag) for _ in range(2)]
        result = summarize_failures(failures)
        assert result is not None
        assert len(result.constraints) <= 5


class TestFailureSummaryFormat:
    def test_format_for_prompt(self):
        summary = FailureSummary(
            constraints=[
                "Use pathlib instead of os",
                "Match the .pyi return type",
            ],
            raw_text="[attempt 1] diagnostic text",
        )
        formatted = summary.format_for_prompt()
        assert "- Use pathlib instead of os" in formatted
        assert "- Match the .pyi return type" in formatted
