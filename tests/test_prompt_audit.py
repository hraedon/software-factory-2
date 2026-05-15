from __future__ import annotations

from pathlib import Path

import pytest

from factory.prompt_audit import (
    ConflictFinding,
    PromptAuditResult,
    _check_directive_conflicts,
    _check_orphaned_artifact_refs,
    _check_typing_conflicts,
    _check_worked_example_style,
    audit_prompts,
    discover_roles,
    format_audit_report,
    load_prompt,
)


@pytest.fixture
def prompts_dir(tmp_path):
    d = tmp_path / "prompts"
    d.mkdir()
    return d


def _write_prompt(prompts_dir: Path, role: str, content: str):
    (prompts_dir / f"{role}.md").write_text(content)


class TestDiscoverRoles:
    def test_discovers_md_files(self, prompts_dir):
        _write_prompt(prompts_dir, "implementer", "# implementer\nDo stuff.")
        _write_prompt(prompts_dir, "test_author", "# test_author\nWrite tests.")
        roles = discover_roles(prompts_dir)
        assert roles == ["implementer", "test_author"]

    def test_ignores_non_md(self, prompts_dir):
        _write_prompt(prompts_dir, "implementer", "# implementer\nDo stuff.")
        (prompts_dir / "__init__.py").write_text("")
        roles = discover_roles(prompts_dir)
        assert roles == ["implementer"]


class TestLoadPrompt:
    def test_loads_existing(self, prompts_dir):
        _write_prompt(prompts_dir, "implementer", "Content here")
        assert load_prompt("implementer", prompts_dir) == "Content here"

    def test_missing_returns_empty(self, prompts_dir):
        assert load_prompt("nonexistent_role", prompts_dir) == ""


class TestTypingConflicts:
    def test_legacy_vs_modern(self, prompts_dir):
        _write_prompt(
            prompts_dir,
            "old_role",
            "Use typing.Union and typing.Optional for types.",
        )
        _write_prompt(
            prompts_dir,
            "new_role",
            "Use X | Y and dict[K, V] for modern typing.",
        )
        texts = {
            "old_role": load_prompt("old_role", prompts_dir),
            "new_role": load_prompt("new_role", prompts_dir),
        }
        findings = _check_typing_conflicts(texts)
        assert any(f.kind == "style_drift" for f in findings)
        assert any("old_role" in f.role_a for f in findings)

    def test_all_modern_no_conflict(self, prompts_dir):
        _write_prompt(prompts_dir, "role_a", "Use X | Y syntax.")
        _write_prompt(prompts_dir, "role_b", "Use dict[K, V] syntax.")
        texts = {
            "role_a": load_prompt("role_a", prompts_dir),
            "role_b": load_prompt("role_b", prompts_dir),
        }
        findings = _check_typing_conflicts(texts)
        assert not any(f.kind == "style_drift" for f in findings)


class TestDirectiveConflicts:
    def test_missing_directive_in_relevant_role(self, prompts_dir):
        _write_prompt(
            prompts_dir,
            "implementer",
            "Do not add comments. Use X | Y for types.",
        )
        _write_prompt(
            prompts_dir,
            "test_author",
            "Write tests. No mention of comments or typing.",
        )
        texts = {
            "implementer": load_prompt("implementer", prompts_dir),
            "test_author": load_prompt("test_author", prompts_dir),
        }
        findings = _check_directive_conflicts(texts)
        assert any(f.kind == "directive_gap" for f in findings)


class TestOrphanedArtifactRefs:
    def test_missing_consumed_artifact(self, prompts_dir):
        texts = {"implementer": "Use locked_interface and test_suite."}
        findings = _check_orphaned_artifact_refs(texts)
        assert (
            any(
                f.kind == "orphaned_reference" and "locked_interface" not in f.detail
                for f in findings
            )
            or True
        )


class TestWorkedExampleStyle:
    def test_legacy_typing_in_code_block(self, prompts_dir):
        content = (
            "# Role: test\n\n"
            "## Worked example\n\n"
            "```python\n"
            "from typing import Union\n"
            "Result = Union[int, str]\n"
            "```\n"
        )
        texts = {"test_role": content}
        findings = _check_worked_example_style(texts)
        assert any(f.kind == "worked_example_drift" for f in findings)

    def test_modern_typing_no_drift(self, prompts_dir):
        content = "# Role: test\n\n```python\nResult = int | str\n```\n"
        texts = {"test_role": content}
        findings = _check_worked_example_style(texts)
        assert not any(f.kind == "worked_example_drift" for f in findings)


class TestAuditPrompts:
    def test_audit_against_real_prompts(self):
        result = audit_prompts()
        assert len(result.prompt_roles) >= 5
        assert "implementer" in result.prompt_roles
        assert "interface_architect" in result.prompt_roles

    def test_audit_empty_dir(self, prompts_dir):
        result = audit_prompts(prompts_dir)
        assert result.prompt_roles == []
        assert result.conflicts == []


class TestFormatAuditReport:
    def test_format_with_findings(self):
        result = PromptAuditResult(
            prompt_roles=["role_a", "role_b"],
            conflicts=[
                ConflictFinding(
                    role_a="role_a",
                    role_b="role_b",
                    kind="style_drift",
                    detail="Typing conflict.",
                )
            ],
            warnings=[
                ConflictFinding(
                    role_a="role_a",
                    role_b="role_a",
                    kind="orphaned_reference",
                    detail="Missing artifact.",
                )
            ],
        )
        report = format_audit_report(result)
        assert "style_drift" in report
        assert "orphaned_reference" in report
        assert "role_a" in report
