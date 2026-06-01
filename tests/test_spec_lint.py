from __future__ import annotations

from factory.spec_lint import (
    check_ac_bullets_well_formed,
    check_ac_concreteness,
    check_ac_count_within_band,
    check_ac_section_exists,
)

_GOOD_SPEC = (
    "## Overview\n"
    "A parser.\n"
    "\n"
    "## Acceptance Criteria\n"
    "\n"
    "- AC-01: accepts valid input\n"
    "- AC-02: rejects bad input\n"
    "- AC-03: returns result\n"
)

_NO_AC_SPEC = "## Overview\nA parser.\n"

_NO_BULLETS_SPEC = (
    "## Overview\nA parser.\n\n## Acceptance Criteria\n\nThe parser must work correctly.\n"
)


class TestCheckAcSectionExists:
    def test_passes_when_ac_present(self):
        assert check_ac_section_exists("spec.md", _GOOD_SPEC) is None

    def test_fails_when_no_ac(self):
        f = check_ac_section_exists("spec.md", _NO_AC_SPEC)
        assert f is not None
        assert f.level == "ERROR"
        assert "No" in f.message


class TestCheckAcBulletsWellFormed:
    def test_passes_on_good_bullets(self):
        findings = check_ac_bullets_well_formed("spec.md", _GOOD_SPEC)
        assert len(findings) == 0

    def test_fails_on_no_bullets(self):
        findings = check_ac_bullets_well_formed("spec.md", _NO_BULLETS_SPEC)
        assert len(findings) == 1
        assert findings[0].level == "ERROR"

    def test_fails_on_duplicates(self):
        spec = "## Acceptance Criteria\n- AC-01: foo\n- AC-01: bar\n"
        findings = check_ac_bullets_well_formed("spec.md", spec)
        assert len(findings) == 1
        assert "duplicate" in findings[0].message.lower()

    def test_accepts_backtick_format(self):
        spec = "## Acceptance Criteria\n- `AC-01`: foo\n- `AC-02`: bar\n"
        findings = check_ac_bullets_well_formed("spec.md", spec)
        assert len(findings) == 0


class TestCheckAcCountWithinBand:
    def test_passes_in_band(self):
        assert check_ac_count_within_band("spec.md", _GOOD_SPEC) is None

    def test_warns_over_cap(self):
        acs = "\n".join(f"- AC-{i:02d}: item {i}" for i in range(1, 11))
        spec = f"## Acceptance Criteria\n{acs}\n"
        f = check_ac_count_within_band("spec.md", spec)
        assert f is not None
        assert f.level == "WARN"
        assert "10 ACs" in f.message


class TestCheckAcConcreteness:
    def test_passes_on_concrete_ac(self):
        spec = (
            "## Acceptance Criteria\n"
            "- AC-01: Given 25 links in the database, returns `list[Link]`\n"
        )
        findings = check_ac_concreteness("spec.md", spec)
        assert len(findings) == 0

    def test_warns_on_vague_ac(self):
        spec = (
            "## Acceptance Criteria\n- AC-01: The response should be user-friendly and readable\n"
        )
        findings = check_ac_concreteness("spec.md", spec)
        assert len(findings) == 1
        assert findings[0].level == "WARN"
        assert findings[0].check == "ac_concreteness"

    def test_warns_on_no_observable_assertion(self):
        spec = "## Acceptance Criteria\n- AC-01: The system processes the request\n"
        findings = check_ac_concreteness("spec.md", spec)
        assert len(findings) == 1
        assert findings[0].level == "WARN"
        assert "concrete" in findings[0].message.lower()

    def test_passes_on_http_status_code(self):
        spec = (
            "## Acceptance Criteria\n- AC-01: POST /links returns HTTP 201 with Location header\n"
        )
        findings = check_ac_concreteness("spec.md", spec)
        assert len(findings) == 0

    def test_passes_on_error_type(self):
        spec = "## Acceptance Criteria\n- AC-01: raises `ValueError` on invalid input\n"
        findings = check_ac_concreteness("spec.md", spec)
        assert len(findings) == 0

    def test_passes_on_numeric_comparison(self):
        spec = "## Acceptance Criteria\n- AC-01: result count is >= 0\n"
        findings = check_ac_concreteness("spec.md", spec)
        assert len(findings) == 0

    def test_vague_with_concrete_override_passes(self):
        spec = (
            "## Acceptance Criteria\n"
            "- AC-01: user-friendly error message contains the status code 422\n"
        )
        findings = check_ac_concreteness("spec.md", spec)
        assert len(findings) == 0

    def test_heading_format_acs_checked(self):
        spec = "## AC-01: Response Format\nThe response should be readable\n"
        findings = check_ac_concreteness("spec.md", spec)
        assert len(findings) == 1
