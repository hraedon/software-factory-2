from __future__ import annotations

from factory.spec_lint import (
    LintResult,
    _extract_acs,
    check_ac_bullets_well_formed,
    check_ac_count_within_band,
    check_ac_section_exists,
    check_ac_single_concern,
    check_ac_symbol_references_resolve,
    check_spec_word_count,
    format_lint_results,
    spec_lint,
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

    def test_errors_on_zero(self):
        f = check_ac_count_within_band("spec.md", _NO_BULLETS_SPEC)
        assert f is not None
        assert f.level == "ERROR"


class TestCheckAcSymbolReferencesResolve:
    def test_passes_with_known_symbols(self):
        export_map = {"cert_model": {"Certificate", "parse_cert"}}
        spec = "## Acceptance Criteria\n- AC-01: `parse_cert` works\n"
        findings = check_ac_symbol_references_resolve("spec.md", spec, export_map)
        assert len(findings) == 0

    def test_warns_on_unknown_symbol(self):
        export_map = {"cert_model": {"Certificate"}}
        spec = "## Acceptance Criteria\n- AC-01: `nonexistent_func` is called\n"
        findings = check_ac_symbol_references_resolve("spec.md", spec, export_map)
        assert len(findings) == 1
        assert findings[0].level == "WARN"
        assert "nonexistent_func" in findings[0].message

    def test_no_findings_without_export_map(self):
        spec = "## Acceptance Criteria\n- AC-01: `whatever` works\n"
        findings = check_ac_symbol_references_resolve("spec.md", spec, None)
        assert len(findings) == 0

    def test_allows_symbols_declared_in_spec(self):
        export_map = {"dep": {"Foo"}}
        spec = "class MyType:\n    pass\n\n## Acceptance Criteria\n- AC-01: `MyType` is used\n"
        findings = check_ac_symbol_references_resolve("spec.md", spec, export_map)
        assert len(findings) == 0


class TestCheckAcSingleConcern:
    def test_passes_on_single_concern(self):
        findings = check_ac_single_concern("spec.md", _GOOD_SPEC)
        assert len(findings) == 0

    def test_warns_on_multiple_conjunctions(self):
        spec = "## Acceptance Criteria\n- AC-01: accepts input and rejects bad and returns result\n"
        findings = check_ac_single_concern("spec.md", spec)
        assert len(findings) == 1
        assert findings[0].level == "WARN"


class TestCheckSpecWordCount:
    def test_passes_under_cap(self):
        assert check_spec_word_count("spec.md", _GOOD_SPEC) is None

    def test_warns_over_cap(self):
        long_spec = "## Overview\n" + "word " * 900
        f = check_spec_word_count("spec.md", long_spec)
        assert f is not None
        assert f.level == "WARN"


class TestSpecLint:
    def test_good_spec_passes(self):
        result = spec_lint("spec.md", _GOOD_SPEC)
        assert result.passed
        assert len(result.findings) == 0

    def test_no_ac_fails(self):
        result = spec_lint("spec.md", _NO_AC_SPEC)
        assert not result.passed
        assert len(result.errors) == 1

    def test_result_properties(self):
        result = LintResult()
        assert result.passed
        assert len(result.errors) == 0
        assert len(result.warnings) == 0


class TestFormatLintResults:
    def test_formats_pass(self):
        results = [("spec.md", LintResult())]
        text = format_lint_results(results)
        assert "PASS" in text
        assert "Summary:" in text

    def test_formats_errors(self):
        from factory.spec_lint import LintFinding

        result = LintResult(
            findings=[
                LintFinding(
                    spec_name="bad.md",
                    level="ERROR",
                    check="ac_section_exists",
                    message="No AC section",
                )
            ]
        )
        results = [("bad.md", result)]
        text = format_lint_results(results)
        assert "FAIL" in text
        assert "ERROR" in text
        assert "1 errors" in text


class TestExtractAcsHeadingPerAcFormat:
    _HEADING_SPEC = (
        "# Interface Specification: Parser\n\n"
        "## Dependencies\nNone.\n\n"
        "## AC-01: Parse Input\n"
        "A `parse_certificate` function must accept DER bytes.\n\n"
        "## AC-02: Error Handling\n"
        "Must return `MalformedCertificateError` on bad input.\n\n"
        "## AC-03: Fingerprint\n"
        "Must expose `fingerprint_sha256`.\n"
    )

    def test_extracts_heading_acs(self):
        acs = _extract_acs(self._HEADING_SPEC)
        assert len(acs) == 3
        assert acs[0][0] == "AC-01"
        assert "parse_certificate" in acs[0][1]
        assert acs[1][0] == "AC-02"
        assert acs[2][0] == "AC-03"

    def test_ac_section_exists_passes_for_headings(self):
        f = check_ac_section_exists("spec.md", self._HEADING_SPEC)
        assert f is None

    def test_ac_count_within_band_passes_for_headings(self):
        f = check_ac_count_within_band("spec.md", self._HEADING_SPEC)
        assert f is None

    def test_ac_bullets_well_formed_passes_for_headings(self):
        findings = check_ac_bullets_well_formed("spec.md", self._HEADING_SPEC)
        assert len(findings) == 0

    def test_single_concern_for_heading_spec(self):
        findings = check_ac_single_concern("spec.md", self._HEADING_SPEC)
        assert len(findings) == 0

    def test_full_lint_passes_for_heading_spec(self):
        result = spec_lint("spec.md", self._HEADING_SPEC)
        assert result.passed
        assert len(result.errors) == 0

    def test_heading_spec_with_many_acs_warns(self):
        acs = "\n\n".join(f"## AC-{i:02d}: Item {i}\nShort desc {i}." for i in range(1, 11))
        spec = f"# Spec\n\n{acs}\n"
        f = check_ac_count_within_band("spec.md", spec)
        assert f is not None
        assert f.level == "WARN"
        assert "10 ACs" in f.message
