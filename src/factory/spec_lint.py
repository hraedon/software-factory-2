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


def _extract_ac_section(spec_text: str) -> tuple[bool, str]:
    in_ac = False
    lines: list[str] = []
    for line in spec_text.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("## acceptance criteria"):
            in_ac = True
            continue
        if in_ac and stripped.startswith("## "):
            break
        if in_ac:
            lines.append(line)
    return in_ac, "\n".join(lines)


def _parse_ac_bullets(ac_text: str) -> list[tuple[str, str]]:
    bullets: list[tuple[str, str]] = []
    for line in ac_text.splitlines():
        stripped = line.strip()
        m = re.match(r"^- `(AC-\d+)`:\s*(.*)", stripped)
        if m:
            bullets.append((m.group(1), m.group(2)))
            continue
        m = re.match(r"^-\s*(AC-\d+):\s*(.*)", stripped)
        if m:
            bullets.append((m.group(1), m.group(2)))
    return bullets


def _extract_backtick_symbols(text: str) -> list[str]:
    return re.findall(r"`([a-zA-Z_][a-zA-Z0-9_]*)`", text)


def check_ac_section_exists(spec_name: str, spec_text: str) -> LintFinding | None:
    has_ac, _ = _extract_ac_section(spec_text)
    if not has_ac:
        return LintFinding(
            spec_name=spec_name,
            level="ERROR",
            check="ac_section_exists",
            message="No '## Acceptance Criteria' section found",
        )
    return None


def check_ac_bullets_well_formed(spec_name: str, spec_text: str) -> list[LintFinding]:
    _, ac_text = _extract_ac_section(spec_text)
    bullets = _parse_ac_bullets(ac_text)
    findings: list[LintFinding] = []

    if not bullets:
        non_empty = [
            ln for ln in ac_text.splitlines() if ln.strip() and not ln.strip().startswith("#")
        ]
        if non_empty:
            findings.append(
                LintFinding(
                    spec_name=spec_name,
                    level="ERROR",
                    check="ac_bullets_well_formed",
                    message="AC section has content but no well-formed bullets "
                    "(expected: `- AC-N: description` or `- `AC-N`: description`)",
                )
            )
        return findings

    seen_ids: dict[str, int] = {}
    for ac_id, _desc in bullets:
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
    _, ac_text = _extract_ac_section(spec_text)
    bullets = _parse_ac_bullets(ac_text)
    count = len(bullets)

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

    _, ac_text = _extract_ac_section(spec_text)
    bullets = _parse_ac_bullets(ac_text)
    findings: list[LintFinding] = []

    all_exports: set[str] = set()
    for symbols in export_map.values():
        all_exports.update(symbols)

    spec_own_names = set(re.findall(r"def\s+(\w+)", spec_text))
    spec_own_names |= set(re.findall(r"class\s+(\w+)", spec_text))

    for ac_id, desc in bullets:
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
    _, ac_text = _extract_ac_section(spec_text)
    bullets = _parse_ac_bullets(ac_text)
    findings: list[LintFinding] = []

    for ac_id, desc in bullets:
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
