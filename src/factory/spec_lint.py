from __future__ import annotations

import re
from dataclasses import dataclass, field

from factory.constants import AC_SOFT_CAP, SPEC_WORD_COUNT_SOFT_CAP


@dataclass
class LintFinding:
    spec_name: str
    level: str
    check: str
    message: str


@dataclass
class LintResult:
    findings: list[LintFinding] = field(default_factory=list)

    @property
    def errors(self) -> list[LintFinding]:
        return [f for f in self.findings if f.level == "ERROR"]

    @property
    def warnings(self) -> list[LintFinding]:
        return [f for f in self.findings if f.level == "WARN"]

    @property
    def passed(self) -> bool:
        return len(self.errors) == 0

    def passed_strict(self) -> bool:
        return len(self.findings) == 0


def _extract_acs(spec_text: str) -> list[tuple[str, str]]:
    """Extract (AC-id, body-text) pairs from a spec.

    Supports two formats:
    1. Section-heading per AC: ``## AC-01: Title`` followed by body text until
       the next ``## AC-NN:`` heading or end of spec.
    2. Bulleted AC section: ``## Acceptance Criteria`` section containing
       ``- `AC-01`: description`` or ``- AC-01: description`` lines.

    Returns a list of (AC-id, body_text) pairs.  *body_text* is the full
    multi-line content for heading-style ACs, or the single-line description
    for bulleted ACs.
    """
    acs: list[tuple[str, str]] = []
    lines = spec_text.splitlines()

    heading_ids = []
    for line in lines:
        m = re.match(r"^##\s+(AC-\d+)\s*:\s*(.*)", line, re.IGNORECASE)
        if m:
            heading_ids.append(m.group(1))

    if heading_ids:
        current_id: str | None = None
        current_body_lines: list[str] = []
        for line in lines:
            m = re.match(r"^##\s+(AC-\d+)\s*:\s*(.*)", line, re.IGNORECASE)
            if m:
                if current_id is not None:
                    acs.append((current_id, "\n".join(current_body_lines).strip()))
                current_id = m.group(1)
                current_body_lines = [m.group(2)]
                continue
            if current_id is not None:
                if line.strip().startswith("## "):
                    acs.append((current_id, "\n".join(current_body_lines).strip()))
                    current_id = None
                    current_body_lines = []
                    continue
                current_body_lines.append(line)
        if current_id is not None:
            acs.append((current_id, "\n".join(current_body_lines).strip()))
        return acs

    in_ac_section = False
    for line in lines:
        stripped = line.strip()
        if stripped.lower().startswith("## acceptance criteria"):
            in_ac_section = True
            continue
        if in_ac_section and stripped.startswith("## "):
            break
        if not in_ac_section:
            continue
        m = re.match(r"^- `(AC-\d+)`:\s*(.*)", stripped)
        if m:
            acs.append((m.group(1), m.group(2)))
            continue
        m = re.match(r"^-\s*(AC-\d+):\s*(.*)", stripped)
        if m:
            acs.append((m.group(1), m.group(2)))
    return acs


def _extract_backtick_symbols(text: str) -> list[str]:
    return re.findall(r"`([a-zA-Z_][a-zA-Z0-9_]*)`", text)


def check_ac_section_exists(spec_name: str, spec_text: str) -> LintFinding | None:
    acs = _extract_acs(spec_text)
    has_ac_section = bool(acs)
    ac_heading_pat = r"^##\s+AC-\d+\s*:"
    has_heading = bool(re.search(ac_heading_pat, spec_text, re.IGNORECASE | re.MULTILINE))
    ac_section_pat = r"^##\s+acceptance criteria"
    has_bulleted = bool(re.search(ac_section_pat, spec_text, re.IGNORECASE | re.MULTILINE))
    if not has_ac_section and not has_heading and not has_bulleted:
        return LintFinding(
            spec_name=spec_name,
            level="ERROR",
            check="ac_section_exists",
            message="No '## Acceptance Criteria' section or '## AC-NN:' headings found",
        )
    return None


def check_ac_bullets_well_formed(spec_name: str, spec_text: str) -> list[LintFinding]:
    acs = _extract_acs(spec_text)
    findings: list[LintFinding] = []

    if not acs:
        ac_heading_pat = r"^##\s+AC-\d+\s*:"
        has_ac_heading = bool(re.search(ac_heading_pat, spec_text, re.IGNORECASE | re.MULTILINE))
        ac_section_pat = r"^##\s+acceptance criteria"
        has_ac_section = bool(re.search(ac_section_pat, spec_text, re.IGNORECASE | re.MULTILINE))
        if has_ac_heading or has_ac_section:
            findings.append(
                LintFinding(
                    spec_name=spec_name,
                    level="ERROR",
                    check="ac_bullets_well_formed",
                    message="AC section/heading found but no parseable ACs",
                )
            )
        return findings

    seen_ids: dict[str, int] = {}
    for ac_id, _desc in acs:
        count = seen_ids.get(ac_id, 0) + 1
        seen_ids[ac_id] = count

    for ac_id, count in seen_ids.items():
        if count > 1:
            findings.append(
                LintFinding(
                    spec_name=spec_name,
                    level="ERROR",
                    check="ac_bullets_well_formed",
                    message=f"{ac_id} appears {count} times (duplicate AC numbers)",
                )
            )

    return findings


def check_ac_count_within_band(spec_name: str, spec_text: str) -> LintFinding | None:
    acs = _extract_acs(spec_text)
    count = len(acs)

    if count < 1:
        return LintFinding(
            spec_name=spec_name,
            level="ERROR",
            check="ac_count",
            message="No ACs found (minimum: 1)",
        )
    if count > AC_SOFT_CAP:
        return LintFinding(
            spec_name=spec_name,
            level="WARN",
            check="ac_count",
            message=f"{count} ACs (soft cap: {AC_SOFT_CAP})",
        )
    return None


def check_ac_symbol_references_resolve(
    spec_name: str,
    spec_text: str,
    export_map: dict[str, set[str]] | None = None,
) -> list[LintFinding]:
    if not export_map:
        return []

    acs = _extract_acs(spec_text)
    findings: list[LintFinding] = []

    all_exports: set[str] = set()
    for symbols in export_map.values():
        all_exports.update(symbols)

    spec_own_names = set(re.findall(r"def\s+(\w+)", spec_text))
    spec_own_names |= set(re.findall(r"class\s+(\w+)", spec_text))

    for ac_id, desc in acs:
        symbols = _extract_backtick_symbols(desc)
        for sym in symbols:
            if sym in all_exports:
                continue
            if sym in spec_own_names:
                continue
            if re.match(r"^AC-\d+$", sym):
                continue
            findings.append(
                LintFinding(
                    spec_name=spec_name,
                    level="WARN",
                    check="ac_symbol_references",
                    message=(
                        f"{ac_id} references `{sym}` which is not in any locked "
                        f"dep exports and not declared in this spec"
                    ),
                )
            )

    return findings


def check_ac_single_concern(spec_name: str, spec_text: str) -> list[LintFinding]:
    acs = _extract_acs(spec_text)
    findings: list[LintFinding] = []

    for ac_id, desc in acs:
        and_count = len(re.findall(r"\band\b", desc, re.IGNORECASE))
        or_count = len(re.findall(r"\bor\b", desc, re.IGNORECASE))
        if and_count + or_count > 1:
            findings.append(
                LintFinding(
                    spec_name=spec_name,
                    level="WARN",
                    check="ac_single_concern",
                    message=(
                        f"{ac_id} has {and_count} 'and' + {or_count} 'or' "
                        f"(>1 conjunction; may bundle multiple concerns)"
                    ),
                )
            )

    return findings


def check_spec_word_count(spec_name: str, spec_text: str) -> LintFinding | None:
    word_count = len(spec_text.split())
    if word_count > SPEC_WORD_COUNT_SOFT_CAP:
        return LintFinding(
            spec_name=spec_name,
            level="WARN",
            check="spec_word_count",
            message=f"{word_count} words (soft cap: {SPEC_WORD_COUNT_SOFT_CAP})",
        )
    return None


def spec_lint(
    spec_name: str,
    spec_text: str,
    export_map: dict[str, set[str]] | None = None,
) -> LintResult:
    result = LintResult()

    f = check_ac_section_exists(spec_name, spec_text)
    if f:
        result.findings.append(f)
        return result

    result.findings.extend(check_ac_bullets_well_formed(spec_name, spec_text))

    f = check_ac_count_within_band(spec_name, spec_text)
    if f:
        result.findings.append(f)

    result.findings.extend(check_ac_symbol_references_resolve(spec_name, spec_text, export_map))

    result.findings.extend(check_ac_single_concern(spec_name, spec_text))

    f = check_spec_word_count(spec_name, spec_text)
    if f:
        result.findings.append(f)

    return result


def format_lint_results(results: list[tuple[str, LintResult]]) -> str:
    lines: list[str] = []
    total_errors = 0
    total_warnings = 0
    pass_count = 0

    for spec_name, result in results:
        if not result.findings:
            lines.append(f"{spec_name}:")
            lines.append("  PASS")
            pass_count += 1
            continue

        lines.append(f"{spec_name}:")
        for f in result.findings:
            lines.append(f"  {f.level} [{f.check}] {f.message}")
            if f.level == "ERROR":
                total_errors += 1
            else:
                total_warnings += 1

    overall = "FAIL" if total_errors > 0 else ("WARN" if total_warnings > 0 else "PASS")
    header = f"spec_lint: {overall}"
    summary = (
        f"Summary: {pass_count} spec PASS, "
        f"{len(results) - pass_count} spec with findings "
        f"({total_errors} errors, {total_warnings} warnings)"
    )

    return header + "\n\n" + "\n".join(lines) + "\n\n" + summary
