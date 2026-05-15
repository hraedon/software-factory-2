from __future__ import annotations

import textwrap
from unittest.mock import patch

import pytest
import yaml

from scripts.agent_golden_run import (
    DANGER_SIGNALS,
    _check_open_breadcrumbs,
    _cleanup_offered,
    _validate_config,
)


class TestCheckOpenBreadcrumbs:
    def test_no_critical_or_high_items(self, tmp_path):
        readme = tmp_path / "README.md"
        readme.write_text(
            textwrap.dedent("""\
            # Breadcrumbs
            ## Open
            ### Active Bugs & Improvements
            | # | Title | Severity | Status |
            |---|---|---|---|
            | 099 | Some low item | low | proposed |
            ## Resolved
        """)
        )
        with patch("scripts.agent_golden_run.BREADCRUMBS_README", readme):
            result = _check_open_breadcrumbs()
        assert result == []

    def test_critical_items_detected(self, tmp_path):
        readme = tmp_path / "README.md"
        readme.write_text(
            textwrap.dedent("""\
            # Breadcrumbs
            ## Open
            ### Active Bugs & Improvements
            | # | Title | Severity | Status |
            |---|---|---|---|
            | 139 | Infinite retry loop | critical | proposed |
            | 138 | Timeout issue | medium | proposed |
            ## Resolved
        """)
        )
        with patch("scripts.agent_golden_run.BREADCRUMBS_README", readme):
            result = _check_open_breadcrumbs()
        assert len(result) == 1
        assert "BC-139" in result[0]
        assert "critical" in result[0]

    def test_high_items_detected(self, tmp_path):
        readme = tmp_path / "README.md"
        readme.write_text(
            textwrap.dedent("""\
            # Breadcrumbs
            ## Open
            ### Active Bugs & Improvements
            | # | Title | Severity | Status |
            |---|---|---|---|
            | 140 | Agent run protocol | high | proposed |
            ## Resolved
        """)
        )
        with patch("scripts.agent_golden_run.BREADCRUMBS_README", readme):
            result = _check_open_breadcrumbs()
        assert len(result) == 1
        assert "BC-140" in result[0]
        assert "high" in result[0]

    def test_critical_and_high_together(self, tmp_path):
        readme = tmp_path / "README.md"
        readme.write_text(
            textwrap.dedent("""\
            # Breadcrumbs
            ## Open
            ### Active Bugs & Improvements
            | # | Title | Severity | Status |
            |---|---|---|---|
            | 139 | Infinite retry | critical | proposed |
            | 140 | Agent protocol | high | proposed |
            | 138 | Timeout | medium | proposed |
            ## Resolved
        """)
        )
        with patch("scripts.agent_golden_run.BREADCRUMBS_README", readme):
            result = _check_open_breadcrumbs()
        assert len(result) == 2

    def test_missing_readme_returns_empty(self, tmp_path):
        readme = tmp_path / "nonexistent.md"
        with patch("scripts.agent_golden_run.BREADCRUMBS_README", readme):
            result = _check_open_breadcrumbs()
        assert result == []

    def test_resolved_section_ignored(self, tmp_path):
        readme = tmp_path / "README.md"
        readme.write_text(
            textwrap.dedent("""\
            # Breadcrumbs
            ## Open
            ### Active Bugs & Improvements
            | # | Title | Severity | Status |
            |---|---|---|---|
            ## Resolved
            | # | Title | Severity | Resolution |
            |---|---|---|---|
            | 139 | Infinite retry | critical | Fixed |
        """)
        )
        with patch("scripts.agent_golden_run.BREADCRUMBS_README", readme):
            result = _check_open_breadcrumbs()
        assert result == []


class TestValidateConfig:
    def test_full_config(self, tmp_path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text(
            yaml.dump(
                {
                    "project_name": "test_project",
                    "workspace_root": "/tmp/sf2-test",
                    "attempt_threshold": 3,
                    "workflow_version": 4,
                    "inner_gate_retries": 2,
                    "jury_quorum": 2,
                }
            )
        )
        result = _validate_config(cfg)
        assert result["project_name"] == "test_project"
        assert result["workspace_root"] == "/tmp/sf2-test"
        assert result["attempt_threshold"] == 3
        assert result["workflow_version"] == 4
        assert result["inner_gate_retries"] == 2
        assert result["jury_quorum"] == 2

    def test_defaults(self, tmp_path):
        cfg = tmp_path / "config.yaml"
        cfg.write_text(yaml.dump({"project_name": "minimal"}))
        result = _validate_config(cfg)
        assert result["project_name"] == "minimal"
        assert result["workspace_root"] == ""
        assert result["attempt_threshold"] == 999
        assert result["workflow_version"] == 0
        assert result["inner_gate_retries"] == 0
        assert result["jury_quorum"] == 0


class TestDangerSignals:
    @pytest.mark.parametrize(
        "name,pattern,matching_line",
        [
            (
                "claim_near_budget",
                DANGER_SIGNALS[0][1],
                "2026-05-14 10:00:00 [WARN] claim_near_budget attempt=3 threshold=3",
            ),
            (
                "gate_fail_cross_family_review",
                DANGER_SIGNALS[1][1],
                "2026-05-14 10:00:00 [INFO] gate_failed cross_family_review work_item=abc",
            ),
            (
                "gate_fail_jury",
                DANGER_SIGNALS[2][1],
                "2026-05-14 10:00:00 [INFO] gate_failed jury work_item=xyz",
            ),
            (
                "channel_invoke_failed",
                DANGER_SIGNALS[3][1],
                "2026-05-14 10:00:00 [ERROR] channel_invoke_failed timeout=600",
            ),
        ],
    )
    def test_pattern_matches(self, name, pattern, matching_line):
        assert pattern.search(matching_line), f"Pattern for {name} should match"

    @pytest.mark.parametrize(
        "name,pattern,non_matching_line",
        [
            (
                "claim_near_budget",
                DANGER_SIGNALS[0][1],
                "2026-05-14 10:00:00 [INFO] locked work_item=abc",
            ),
            (
                "gate_fail_cross_family_review",
                DANGER_SIGNALS[1][1],
                "2026-05-14 10:00:00 [INFO] gate_failed import_check work_item=abc",
            ),
            (
                "gate_fail_jury",
                DANGER_SIGNALS[2][1],
                "2026-05-14 10:00:00 [INFO] gate_failed ruff work_item=xyz",
            ),
            (
                "channel_invoke_failed",
                DANGER_SIGNALS[3][1],
                "2026-05-14 10:00:00 [INFO] channel_invoke succeeded",
            ),
        ],
    )
    def test_pattern_does_not_match(self, name, pattern, non_matching_line):
        assert not pattern.search(non_matching_line), f"Pattern for {name} should not match"


class TestCleanup:
    def test_cleanup_removes_workspace_and_logs(self, tmp_path):
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        (workspace / "artifact.py").write_text("pass")
        log1 = tmp_path / "gr-test-runner.log"
        log2 = tmp_path / "gr-test-gate.log"
        log3 = tmp_path / "gr-test-scheduler.log"
        for f in (log1, log2, log3):
            f.write_text("log content")

        _cleanup_offered(str(workspace), "gr-test", log_dir=str(tmp_path))

        assert not workspace.exists()
        assert not log1.exists()
        assert not log2.exists()
        assert not log3.exists()

    def test_cleanup_nonexistent_workspace_is_safe(self, tmp_path):
        workspace = tmp_path / "nonexistent"
        log1 = tmp_path / "gr-test-runner.log"
        log1.write_text("log")

        _cleanup_offered(str(workspace), "gr-test", log_dir=str(tmp_path))

        assert not log1.exists()

    def test_cleanup_removes_isolated_opencode_db(self, tmp_path):
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        log1 = tmp_path / "gr-test-runner.log"
        log1.write_text("log")
        isolated_db = tmp_path / "isolated-opencode-data"
        isolated_db.mkdir()
        (isolated_db / "opencode.db").write_text("db")

        _cleanup_offered(
            str(workspace),
            "gr-test",
            log_dir=str(tmp_path),
            xdg_data_home=isolated_db,
        )

        assert not workspace.exists()
        assert not log1.exists()
        assert not isolated_db.exists()
