"""Prompt conflict detection and directive gap analysis.

Phase 6: pending integration (RFC-001). Implemented and tested but not wired
into production paths. Tracked in BC-206. Integrate when prompt template
management requires automated conflict detection.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

PROMPTS_DIR = Path(__file__).parent / "prompts"

_FORBIDDEN_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    "typing.Union": [re.compile(r"typing\.Union\b"), re.compile(r"\bUnion\[")],
    "typing.Optional": [re.compile(r"typing\.Optional\b"), re.compile(r"\bOptional\[")],
    "typing.Dict": [re.compile(r"typing\.Dict\b"), re.compile(r"\bDict\[")],
    "typing.List": [re.compile(r"typing\.List\b"), re.compile(r"\bList\[")],
    "typing.Tuple": [re.compile(r"typing\.Tuple\b"), re.compile(r"\bTuple\[")],
    "typing.Set": [re.compile(r"typing\.Set\b"), re.compile(r"\bSet\[")],
}

_REQUIRED_PATTERNS: dict[str, list[re.Pattern[str]]] = {
    "modern_union": [re.compile(r"X \| Y|str \| None|int \| None|\w+ \| None")],
    "lowercase_generics": [re.compile(r"dict\[|list\[|set\[|tuple\[")],
}

_PROHIBITION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"Do not\s+.*(?:import from|use)\s+.*(?:_impl|implementation)"),
    re.compile(r"Do not\s+.*(?:write|add|produce)\s+.*(?:comments|comment)"),
    re.compile(r"Do not\s+.*(?:modify|change)\s+.*(?:interface|\.pyi|contract)"),
    re.compile(r"Do not\s+.*(?:add|introduce)\s+.*(?:new public symbols|abstractions)"),
    re.compile(r"Must\s+.*(?:import from|use)\s+.*(?:locked interface|\.pyi)"),
]

_DIRECTIVE_PATTERNS: dict[str, re.Pattern[str]] = {
    "import_from_interface": re.compile(
        r"[Ii]mport\s+(?:only\s+)?from\s+(?:the\s+)?(?:locked\s+)?interface"
    ),
    "no_import_from_impl": re.compile(r"[Dd]o not import from.*(?:_impl|implementation|internal)"),
    "no_comments": re.compile(r"[Dd]o not\s+(?:add|produce|write).*comments"),
    "no_modify_interface": re.compile(r"[Dd]o not\s+(?:modify|change).*interface"),
    "no_new_public_symbols": re.compile(r"[Dd]o not\s+(?:add|introduce).*new public symbols"),
    "no_abstractions": re.compile(r"[Dd]o not\s+(?:add|create).*(?:abstractions?|protocols?|ABC)"),
    "no_globals": re.compile(r"[Dd]o not.*(?:global|module-level state|singleton)"),
    "must_use_modern_typing": re.compile(r"(?:Use|must use).*(?:modern|X \| Y|lowercase generics)"),
    "must_match_signatures": re.compile(r"[Mm]atch.*(?:interface|\.pyi).*(?:signature|exactly)"),
    "no_implementation": re.compile(r"[Dd]o not.*(?:write|produce).*implementation"),
    "must_use_deps": re.compile(r"[Uu]se dependency types.*(?:do not recreate|import from)"),
}

_CONSUMES_MAP: dict[str, list[str]] = {
    "locked_interface": ["test_author", "implementer", "cross_family_reviewer", "frontier_judge"],
    "test_suite": ["implementer", "cross_family_reviewer", "frontier_judge", "integrator"],
    "implementation": ["cross_family_reviewer", "frontier_judge", "integrator"],
    "focal_implementation": ["integrator"],
    "focal_interface": ["integrator"],
    "focal_test_suite": ["integrator"],
    "locked_dependency_*": ["test_author", "implementer", "integrator"],
    "assembled_modules": ["outcome_verifier"],
    "integration_tests": ["outcome_verifier"],
}

_PRODUCES_MAP: dict[str, list[str]] = {
    "interface_architect": ["locked_interface"],
    "test_author": ["test_suite"],
    "implementer": ["implementation", "focal_implementation"],
    "cross_family_reviewer": ["review_verdict"],
    "frontier_judge": ["jury_verdict"],
    "integrator": ["assembled_tree", "integration_tests", "assembled_modules"],
    "outcome_verifier": ["outcome_verdict"],
}

_ARTIFACT_CONSUMES_FROM_PROMPT: dict[str, list[str]] = {
    "interface_architect": [
        "spec_section",
        "ac_ids",
        "glossary",
        "prior_failures",
    ],
    "test_author": [
        "spec_section",
        "ac_ids",
        "locked_interface",
        "locked_dependency_*",
        "glossary",
        "prior_failures",
    ],
    "implementer": [
        "spec_section",
        "ac_ids",
        "locked_interface",
        "locked_dependency_*",
        "test_suite",
        "glossary",
        "prior_failures",
    ],
    "cross_family_reviewer": [
        "spec_section",
        "ac_ids",
        "locked_interface",
        "test_suite",
        "implementation",
        "glossary",
        "prior_failures",
    ],
    "frontier_judge": [
        "spec_section",
        "ac_ids",
        "locked_interface",
        "test_suite",
        "implementation",
        "glossary",
        "prior_failures",
    ],
    "integrator": [
        "spec_section",
        "ac_ids",
        "focal_implementation",
        "focal_interface",
        "focal_test_suite",
        "locked_dependency_*",
        "prior_failures",
    ],
    "outcome_verifier": [
        "spec_section",
        "ac_ids",
        "assembled_modules",
        "integration_tests",
        "glossary",
        "prior_failures",
    ],
}


@dataclass(frozen=True)
class ConflictFinding:
    role_a: str
    role_b: str
    kind: str
    detail: str


@dataclass
class PromptAuditResult:
    conflicts: list[ConflictFinding] = field(default_factory=list)
    warnings: list[ConflictFinding] = field(default_factory=list)
    prompt_roles: list[str] = field(default_factory=list)


def load_prompt(role: str, prompts_dir: Path | None = None) -> str:
    d = prompts_dir or PROMPTS_DIR
    p = d / f"{role}.md"
    if p.exists():
        return p.read_text()
    return ""


def discover_roles(prompts_dir: Path | None = None) -> list[str]:
    d = prompts_dir or PROMPTS_DIR
    roles = []
    for p in sorted(d.glob("*.md")):
        roles.append(p.stem)
    return roles


def audit_prompts(prompts_dir: Path | None = None) -> PromptAuditResult:
    result = PromptAuditResult()
    roles = discover_roles(prompts_dir)
    result.prompt_roles = roles

    texts: dict[str, str] = {}
    for role in roles:
        texts[role] = load_prompt(role, prompts_dir)

    result.conflicts.extend(_check_typing_conflicts(texts))
    result.conflicts.extend(_check_directive_conflicts(texts))
    result.warnings.extend(_check_orphaned_artifact_refs(texts))
    result.warnings.extend(_check_produces_consumes(texts))
    result.warnings.extend(_check_worked_example_style(texts))

    return result


def _check_typing_conflicts(texts: dict[str, str]) -> list[ConflictFinding]:
    findings: list[ConflictFinding] = []
    legacy_roles: list[str] = []
    modern_roles: list[str] = []

    for role, text in texts.items():
        has_legacy = False
        has_modern = False
        for label, patterns in _FORBIDDEN_PATTERNS.items():
            for pat in patterns:
                if pat.search(text):
                    has_legacy = True
        for label, patterns in _REQUIRED_PATTERNS.items():
            for pat in patterns:
                if pat.search(text):
                    has_modern = True
        if has_legacy and not has_modern:
            legacy_roles.append(role)
        elif has_modern and not has_legacy:
            modern_roles.append(role)
        elif has_legacy and has_modern:
            legacy_roles.append(role)

    for legacy_role in legacy_roles:
        for modern_role in modern_roles:
            findings.append(
                ConflictFinding(
                    role_a=legacy_role,
                    role_b=modern_role,
                    kind="style_drift",
                    detail=(
                        f"{legacy_role} uses legacy typing "
                        "(typing.Union/Optional/Dict/List) "
                        f"while {modern_role} requires modern syntax "
                        "(X | Y, dict[K, V]). Code produced under "
                        "legacy conventions will fail gates enforcing "
                        "modern rules."
                    ),
                )
            )

    return findings


def _check_directive_conflicts(texts: dict[str, str]) -> list[ConflictFinding]:
    findings: list[ConflictFinding] = []
    role_directives: dict[str, dict[str, bool]] = {}

    for role, text in texts.items():
        directives: dict[str, bool] = {}
        for label, pattern in _DIRECTIVE_PATTERNS.items():
            directives[label] = bool(pattern.search(text))
        role_directives[role] = directives

    directive_names = set()
    for d in role_directives.values():
        directive_names.update(d.keys())

    for directive in sorted(directive_names):
        roles_with = [r for r, d in role_directives.items() if d.get(directive)]
        roles_without = [r for r, d in role_directives.items() if not d.get(directive)]
        if len(roles_with) >= 1 and len(roles_without) >= 1:
            relevant_without = [
                r for r in roles_without if _role_should_have_directive(r, directive)
            ]
            if relevant_without:
                for missing_role in relevant_without:
                    findings.append(
                        ConflictFinding(
                            role_a=roles_with[0],
                            role_b=missing_role,
                            kind="directive_gap",
                            detail=f"'{directive}' directive present in {', '.join(roles_with)} "
                            f"but missing from {missing_role}. "
                            f"Agents without this constraint may violate it silently.",
                        )
                    )

    return findings


def _role_should_have_directive(role: str, directive: str) -> bool:
    if directive == "no_comments" and role in (
        "test_author",
        "implementer",
        "interface_architect",
    ):
        return True
    if directive == "must_use_modern_typing" and role in (
        "test_author",
        "implementer",
        "interface_architect",
    ):
        return True
    if directive == "must_match_signatures" and role in ("implementer", "integrator"):
        return True
    if directive == "must_use_deps" and role in ("implementer", "test_author", "integrator"):
        return True
    if directive == "no_modify_interface" and role in (
        "implementer",
        "test_author",
        "integrator",
    ):
        return True
    if directive == "no_new_public_symbols" and role in ("implementer",):
        return True
    return False


def _check_orphaned_artifact_refs(texts: dict[str, str]) -> list[ConflictFinding]:
    findings: list[ConflictFinding] = []
    for role, text in texts.items():
        expected = _ARTIFACT_CONSUMES_FROM_PROMPT.get(role, [])
        for artifact in expected:
            artifact_clean = artifact.rstrip("*")
            if artifact_clean not in text and artifact not in text:
                findings.append(
                    ConflictFinding(
                        role_a=role,
                        role_b=role,
                        kind="orphaned_reference",
                        detail=f"Role {role} should consume '{artifact}' per "
                        f"the stage handoff contract but the prompt does not mention it.",
                    )
                )
    return findings


def _check_produces_consumes(texts: dict[str, str]) -> list[ConflictFinding]:
    findings: list[ConflictFinding] = []
    for consumer_role, consumed_artifacts in _CONSUMES_MAP.items():
        consumers = [r for r in texts if r in consumed_artifacts]
        artifact_clean = consumer_role.rstrip("*")
        producers = _PRODUCES_MAP.get(artifact_clean, []) or _PRODUCES_MAP.get(consumer_role, [])
        if not producers and consumer_role not in (
            "spec_section",
            "ac_ids",
            "glossary",
            "prior_failures",
        ):
            has_consumer_mention = any(artifact_clean in texts.get(r, "") for r in texts)
            if consumers and not has_consumer_mention:
                findings.append(
                    ConflictFinding(
                        role_a=consumer_role,
                        role_b=", ".join(consumers),
                        kind="orphaned_consumes",
                        detail=f"Artifact '{consumer_role}' is consumed by {consumers} "
                        f"but no role declares it as produced output.",
                    )
                )
    return findings


def _check_worked_example_style(texts: dict[str, str]) -> list[ConflictFinding]:
    findings: list[ConflictFinding] = []
    for role, text in texts.items():
        in_code_block = False
        code_block_lines: list[str] = []
        for line in text.splitlines():
            if line.strip().startswith("```python"):
                in_code_block = True
                code_block_lines = []
                continue
            if in_code_block and line.strip().startswith("```"):
                in_code_block = False
                code_text = "\n".join(code_block_lines)
                for label, patterns in _FORBIDDEN_PATTERNS.items():
                    for pat in patterns:
                        if pat.search(code_text):
                            findings.append(
                                ConflictFinding(
                                    role_a=role,
                                    role_b=role,
                                    kind="worked_example_drift",
                                    detail=f"Worked example in {role} uses legacy '{label}' "
                                    f"pattern. Downstream gates enforce modern syntax.",
                                )
                            )
                continue
            if in_code_block:
                code_block_lines.append(line)
    return findings


def format_audit_report(result: PromptAuditResult) -> str:
    lines: list[str] = ["# Prompt Audit Report", ""]
    lines.append(f"**Roles audited:** {', '.join(result.prompt_roles)}")
    lines.append(f"**Conflicts:** {len(result.conflicts)}")
    lines.append(f"**Warnings:** {len(result.warnings)}")
    lines.append("")

    if result.conflicts:
        lines.append("## Conflicts")
        lines.append("")
        for f in result.conflicts:
            lines.append(f"- **[{f.kind}]** {f.role_a} vs {f.role_b}: {f.detail}")
        lines.append("")

    if result.warnings:
        lines.append("## Warnings")
        lines.append("")
        for f in result.warnings:
            lines.append(f"- **[{f.kind}]** {f.role_a} vs {f.role_b}: {f.detail}")
        lines.append("")

    if not result.conflicts and not result.warnings:
        lines.append("No conflicts or warnings detected.")

    return "\n".join(lines)
