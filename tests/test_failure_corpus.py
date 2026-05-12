from __future__ import annotations

import json


class TestCorpusRow:
    def test_corpus_row_serialization(self):
        from scripts.build_failure_corpus import CorpusRow

        row = CorpusRow(
            gr_id="GR-019",
            work_item_id="abc123",
            role="implementer",
            channel="opencode",
            attempt=0,
            gate_label="inner_mypy",
            feedback_excerpt="error: incompatible types",
            category=None,
            subcategory=None,
            fixed_on_retry=1,
            fixed_on_retry_label=None,
            model="kimi-k2p6-turbo",
            ts="2026-05-12T03:24:11Z",
        )
        d = row.to_dict()
        assert d["gr_id"] == "GR-019"
        assert d["category"] is None
        serialized = json.dumps(d, sort_keys=True)
        parsed = json.loads(serialized)
        assert parsed["gr_id"] == "GR-019"
        assert parsed["gate_label"] == "inner_mypy"


class TestExtractGrId:
    def test_extracts_gr_from_config_filename(self):
        from scripts.build_failure_corpus import _extract_gr_id

        assert _extract_gr_id("golden-run-019-config.yaml") == "GR-019"
        assert _extract_gr_id("golden-run-006a-config.yaml") == "GR-006a"
        assert _extract_gr_id("/some/path/golden-run-014-config.yaml") == "GR-014"

    def test_falls_back_to_stem(self):
        from scripts.build_failure_corpus import _extract_gr_id

        assert _extract_gr_id("my-config.yaml") == "my-config"


class TestClassifyAuto:
    def test_classifies_ruff_style(self):
        from scripts.build_failure_corpus import _classify_auto, _load_rules

        rules = _load_rules()
        assert rules, "No classification rules loaded"

        cat = _classify_auto("F841 local variable 'x' is assigned but never used", rules)
        assert cat == "ruff_style"

        cat = _classify_auto("E501 line too long", rules)
        assert cat == "ruff_style"

    def test_classifies_import_unknown_symbol(self):
        from scripts.build_failure_corpus import _classify_auto, _load_rules

        rules = _load_rules()
        feedback = "mod.py:12: 'certificate_model' imports unknown symbols: parse_certificate"
        cat = _classify_auto(feedback, rules)
        assert cat == "import_unknown_symbol"

    def test_classifies_import_module_path(self):
        from scripts.build_failure_corpus import _classify_auto, _load_rules

        rules = _load_rules()
        cat = _classify_auto("ModuleNotFoundError: No module named 'foo'", rules)
        assert cat == "import_module_path"

    def test_classifies_channel_failure(self):
        from scripts.build_failure_corpus import _classify_auto, _load_rules

        rules = _load_rules()
        cat = _classify_auto("channel timed out after 300s", rules)
        assert cat == "channel_failure"

    def test_returns_none_for_unknown(self):
        from scripts.build_failure_corpus import _classify_auto, _load_rules

        rules = _load_rules()
        cat = _classify_auto("some completely novel error message", rules)
        assert cat is None


class TestLoadExistingKeys:
    def test_loads_existing_keys(self, tmp_path):
        from scripts.build_failure_corpus import _load_existing_keys

        corpus = tmp_path / "test.jsonl"
        rows = [
            {
                "gr_id": "GR-019",
                "work_item_id": "abc",
                "attempt": 0,
                "gate_label": "inner_mypy",
            },
            {
                "gr_id": "GR-019",
                "work_item_id": "def",
                "attempt": 0,
                "gate_label": "inner_ruff",
            },
        ]
        with open(corpus, "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")

        keys = _load_existing_keys(corpus)
        assert ("GR-019", "abc", 0, "inner_mypy") in keys
        assert ("GR-019", "def", 0, "inner_ruff") in keys
        assert len(keys) == 2

    def test_empty_file(self, tmp_path):
        from scripts.build_failure_corpus import _load_existing_keys

        corpus = tmp_path / "empty.jsonl"
        corpus.touch()
        keys = _load_existing_keys(corpus)
        assert keys == set()

    def test_nonexistent_file(self, tmp_path):
        from scripts.build_failure_corpus import _load_existing_keys

        keys = _load_existing_keys(tmp_path / "nope.jsonl")
        assert keys == set()


class TestAppendRows:
    def test_appends_rows(self, tmp_path):
        from scripts.build_failure_corpus import CorpusRow, append_rows

        path = tmp_path / "corpus.jsonl"
        rows = [
            CorpusRow(
                gr_id="GR-019",
                work_item_id="abc",
                role="implementer",
                channel="opencode",
                attempt=0,
                gate_label="inner_mypy",
                feedback_excerpt="err",
                category="type_mismatch_internal",
                subcategory=None,
                fixed_on_retry=1,
                fixed_on_retry_label=None,
                model=None,
                ts=None,
            ),
        ]
        count = append_rows(path, rows)
        assert count == 1

        with open(path) as f:
            written = [json.loads(line) for line in f]
        assert len(written) == 1
        assert written[0]["category"] == "type_mismatch_internal"

    def test_appends_to_existing(self, tmp_path):
        from scripts.build_failure_corpus import CorpusRow, append_rows

        path = tmp_path / "corpus.jsonl"
        path.write_text('{"existing": true}\n')

        rows = [
            CorpusRow(
                gr_id="GR-020",
                work_item_id="xyz",
                role="test_author",
                channel="opencode",
                attempt=0,
                gate_label="inner_ruff",
                feedback_excerpt="x",
                category="ruff_style",
                subcategory=None,
                fixed_on_retry=None,
                fixed_on_retry_label=None,
                model=None,
                ts=None,
            ),
        ]
        append_rows(path, rows)

        with open(path) as f:
            lines = f.readlines()
        assert len(lines) == 2


class TestCorpusReport:
    def test_generate_report_empty(self):
        from scripts.failure_corpus_report import generate_report

        report = generate_report([])
        assert "No classified rows" in report

    def test_generate_report_with_data(self):
        from scripts.failure_corpus_report import generate_report

        rows = [
            {
                "gr_id": "GR-019",
                "work_item_id": "abc",
                "category": "ruff_style",
                "gate_label": "inner_ruff",
            },
            {
                "gr_id": "GR-019",
                "work_item_id": "def",
                "category": "import_unknown_symbol",
                "gate_label": "inner_import_symbols",
            },
            {
                "gr_id": "GR-019",
                "work_item_id": "ghi",
                "category": "ruff_style",
                "gate_label": "inner_ruff",
            },
        ]
        report = generate_report(rows)
        assert "N=3" in report
        assert "GR-019" in report
        assert "ruff_style" in report
        assert "import_unknown_symbol" in report
        assert "Distribution" in report
        assert "Per-GR breakdown" in report

    def test_generate_report_multi_gr(self):
        from scripts.failure_corpus_report import generate_report

        rows = [
            _row("GR-018", "a", "ruff_style", "inner_ruff"),
            _row("GR-018", "b", "ruff_style", "inner_ruff"),
            _row("GR-019", "c", "import_unknown_symbol", "inner_import_symbols"),
            _row("GR-019", "d", "ruff_style", "inner_ruff"),
        ]
        report = generate_report(rows)
        assert "GR-018" in report
        assert "GR-019" in report

    def test_generate_report_warns_on_high_other(self):
        from scripts.failure_corpus_report import generate_report

        rows = [_row("GR-019", str(i), "other", "inner_mypy") for i in range(15)]
        report = generate_report(rows)
        assert "Taxonomy may need revision" in report

    def test_load_corpus(self, tmp_path):
        from scripts.failure_corpus_report import load_corpus

        path = tmp_path / "test.jsonl"
        with open(path, "w") as f:
            f.write(json.dumps({"gr_id": "GR-019", "category": "ruff_style"}) + "\n")
            f.write("\n")
            f.write("bad json\n")
            f.write(json.dumps({"gr_id": "GR-018", "category": "other"}) + "\n")

        rows = load_corpus(path)
        assert len(rows) == 2
        assert rows[0]["gr_id"] == "GR-019"
        assert rows[1]["gr_id"] == "GR-018"

    def test_trend_arrows(self):
        from scripts.failure_corpus_report import compute_trend

        by_gr_cat = {
            "GR-017": {"ruff_style": 10, "other": 10},
            "GR-018": {"ruff_style": 8, "other": 10},
            "GR-019": {"ruff_style": 2, "other": 10},
        }
        sorted_grs = ["GR-017", "GR-018", "GR-019"]

        trend = compute_trend(by_gr_cat, sorted_grs, "ruff_style")
        assert "\u2193" in trend

        trend_other = compute_trend(by_gr_cat, sorted_grs, "other")
        assert "\u2191" in trend_other

    def test_sort_gr_ids(self):
        from scripts.failure_corpus_report import _sort_gr_ids

        result = _sort_gr_ids({"GR-019", "GR-006a", "GR-014", "GR-001"})
        assert result == ["GR-001", "GR-006a", "GR-014", "GR-019"]


def _row(gr_id, wi_id, category, gate_label):
    return {
        "gr_id": gr_id,
        "work_item_id": wi_id,
        "category": category,
        "gate_label": gate_label,
    }
