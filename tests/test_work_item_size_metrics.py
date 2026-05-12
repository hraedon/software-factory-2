from __future__ import annotations

import csv
import io

from scripts.work_item_size_metrics import (
    SizeRow,
    _count_ac_bullets,
    _word_count,
    rows_to_csv,
)


class TestCountAcBullets:
    def test_counts_bullets_in_ac_section(self):
        spec = (
            "## Overview\n"
            "Some text.\n"
            "\n"
            "## Acceptance Criteria\n"
            "\n"
            "- AC-01: parses valid input\n"
            "- AC-02: rejects invalid input\n"
            "- AC-03: returns error code\n"
            "\n"
            "## Notes\n"
            "More text.\n"
        )
        assert _count_ac_bullets(spec) == 3

    def test_empty_spec(self):
        assert _count_ac_bullets("") == 0

    def test_no_ac_section(self):
        spec = "## Overview\nSome text.\n"
        assert _count_ac_bullets(spec) == 0

    def test_ac_section_at_end(self):
        spec = "## Acceptance Criteria\n\n- AC-01: foo\n- AC-02: bar\n"
        assert _count_ac_bullets(spec) == 2


class TestWordCount:
    def test_counts_words(self):
        assert _word_count("hello world foo") == 3

    def test_empty(self):
        assert _word_count("") == 0


class TestSizeRow:
    def test_row_creation(self):
        row = SizeRow(
            gr_id="GR-019",
            work_item_id="abc",
            role="implementer",
            ac_count=5,
            spec_word_count=200,
            dep_count=2,
            dep_total_pyi_lines=45,
            first_attempt_passed=False,
            retry_count=1,
            gate_label_on_first_fail="inner_mypy",
            locked=True,
        )
        assert row.ac_count == 5
        assert row.first_attempt_passed is False
        assert row.locked is True


class TestRowsToCsv:
    def test_produces_valid_csv(self):
        rows = [
            SizeRow(
                gr_id="GR-019",
                work_item_id="abc",
                role="implementer",
                ac_count=3,
                spec_word_count=100,
                dep_count=1,
                dep_total_pyi_lines=20,
                first_attempt_passed=True,
                retry_count=0,
                gate_label_on_first_fail="",
                locked=True,
            ),
            SizeRow(
                gr_id="GR-019",
                work_item_id="def",
                role="test_author",
                ac_count=8,
                spec_word_count=300,
                dep_count=3,
                dep_total_pyi_lines=80,
                first_attempt_passed=False,
                retry_count=2,
                gate_label_on_first_fail="inner_ruff",
                locked=False,
            ),
        ]
        csv_text = rows_to_csv(rows)
        reader = csv.DictReader(io.StringIO(csv_text))
        parsed = list(reader)
        assert len(parsed) == 2
        assert parsed[0]["ac_count"] == "3"
        assert parsed[0]["first_attempt_passed"] == "True"
        assert parsed[1]["gate_label_on_first_fail"] == "inner_ruff"
        assert parsed[1]["dep_total_pyi_lines"] == "80"

    def test_empty_rows(self):
        csv_text = rows_to_csv([])
        reader = csv.DictReader(io.StringIO(csv_text))
        parsed = list(reader)
        assert len(parsed) == 0
        assert "ac_count" in csv_text
