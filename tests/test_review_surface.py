from __future__ import annotations

import json
from pathlib import Path

from factory.review_surface import (
    CannotProceedDetail,
    ModuleReview,
    ReviewReport,
    render_review_markdown,
    write_review_report,
)


def _make_report(
    pipeline_status: str = "complete",
    locked: int = 3,
    cannot_proceed: int = 0,
    in_progress: int = 0,
    cp_details: list[CannotProceedDetail] | None = None,
) -> ReviewReport:
    modules = [
        ModuleReview(
            module_name="fr01",
            status="locked",
            work_item_id="wi-001",
            work_item_type="interface_spec",
            spec_section_preview="Config loading",
        ),
        ModuleReview(
            module_name="fr02",
            status="locked",
            work_item_id="wi-002",
            work_item_type="interface_spec",
            spec_section_preview="Processing items",
        ),
        ModuleReview(
            module_name="fr03",
            status="locked" if cannot_proceed == 0 else "cannot_proceed",
            work_item_id="wi-003",
            work_item_type="interface_spec",
            spec_section_preview="Output results",
        ),
    ]
    return ReviewReport(
        project_name="test-project",
        pipeline_status=pipeline_status,
        total_items=3,
        locked_items=locked,
        cannot_proceed_items=cannot_proceed,
        in_progress_items=in_progress,
        modules=modules,
        cannot_proceed_details=cp_details or [],
    )


class TestRenderReviewMarkdown:
    def test_complete_pipeline(self):
        report = _make_report()
        md = render_review_markdown(report)

        assert "# Review Report: test-project" in md
        assert "**Status:** complete" in md
        assert "All items locked" in md
        assert "| fr01 | interface_spec | locked |" in md

    def test_partial_pipeline(self):
        cp = CannotProceedDetail(
            module_name="fr03",
            work_item_type="implementation",
            reason="mypy failed after 3 attempts",
        )
        report = _make_report(
            pipeline_status="partial",
            locked=2,
            cannot_proceed=1,
            cp_details=[cp],
        )
        md = render_review_markdown(report)

        assert "**Status:** partial" in md
        assert "Partial completion" in md
        assert "## Cannot-proceed details" in md
        assert "mypy failed after 3 attempts" in md

    def test_in_progress_pipeline(self):
        report = _make_report(
            pipeline_status="in_progress",
            locked=1,
            in_progress=2,
        )
        md = render_review_markdown(report)

        assert "**Status:** in_progress" in md
        assert "still running" in md


class TestWriteReviewReport:
    def test_writes_markdown_and_json(self, tmp_path: Path):
        report = _make_report()
        output = tmp_path / "review"
        md_path = write_review_report(report, output)

        assert md_path.exists()
        assert (output / "review.json").exists()

        md_content = md_path.read_text()
        assert "# Review Report: test-project" in md_content

        json_data = json.loads((output / "review.json").read_text())
        assert json_data["project_name"] == "test-project"
        assert json_data["locked_items"] == 3
        assert len(json_data["modules"]) == 3

    def test_json_contains_cannot_proceed(self, tmp_path: Path):
        cp = CannotProceedDetail(
            module_name="fr03",
            work_item_type="implementation",
            reason="timeout",
        )
        report = _make_report(
            pipeline_status="partial",
            locked=2,
            cannot_proceed=1,
            cp_details=[cp],
        )
        output = tmp_path / "review"
        write_review_report(report, output)

        json_data = json.loads((output / "review.json").read_text())
        assert len(json_data["cannot_proceed_details"]) == 1
        assert json_data["cannot_proceed_details"][0]["reason"] == "timeout"

    def test_creates_output_dir(self, tmp_path: Path):
        report = _make_report()
        output = tmp_path / "nested" / "review"
        md_path = write_review_report(report, output)

        assert output.exists()
        assert md_path.exists()


class TestModuleSorting:
    def test_locked_modules_first(self):
        report = _make_report(
            pipeline_status="partial",
            locked=2,
            cannot_proceed=1,
        )
        md = render_review_markdown(report)

        lines = md.split("\n")
        table_rows = [row for row in lines if row.startswith("| fr")]
        assert len(table_rows) == 3
        non_locked = [r for r in table_rows if "cannot_proceed" in r]
        locked_rows = [r for r in table_rows if "locked" in r]
        assert len(non_locked) > 0
        first_locked_idx = table_rows.index(locked_rows[0])
        first_non_locked_idx = table_rows.index(non_locked[0])
        assert first_locked_idx < first_non_locked_idx
