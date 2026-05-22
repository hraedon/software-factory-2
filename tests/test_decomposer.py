from __future__ import annotations

import textwrap
from pathlib import Path

import pytest
import yaml

from factory.decomposer import (
    decompose_from_spec_md,
    decompose_from_spec_yaml,
    write_fixture_files,
)


def _write_spec_yaml(tmp_path: Path, data: dict) -> Path:
    tmp_path.mkdir(parents=True, exist_ok=True)
    p = tmp_path / "spec.yaml"
    p.write_text(yaml.dump(data, default_flow_style=False))
    return p


def _make_spec_yaml_data() -> dict:
    return {
        "meta": {"name": "test-spec", "spec_level": 2, "desired_level": 3},
        "glossary": [
            {"term": "widget", "definition": "A unit of work"},
        ],
        "functional_requirements": [
            {"id": "FR-01", "mvp": True, "text": "The system loads config."},
            {"id": "FR-02", "mvp": True, "text": "The system processes items."},
            {"id": "FR-03", "mvp": True, "text": "The system outputs results."},
        ],
        "acceptance_criteria": [
            {"id": "AC-01", "fr_ids": ["FR-01"], "condition": "Config loads"},
            {"id": "AC-02", "fr_ids": ["FR-01"], "condition": "Config validates"},
            {"id": "AC-03", "fr_ids": ["FR-02"], "condition": "Items processed"},
            {"id": "AC-04", "fr_ids": ["FR-02", "FR-03"], "condition": "Results match"},
            {"id": "AC-05", "fr_ids": ["FR-03"], "condition": "Output formatted"},
        ],
        "work_decomposition": {
            "value_phases": [
                {"phase": 1, "label": "MVP", "fr_ids": ["FR-01", "FR-02", "FR-03"]},
            ],
            "dependency_hints": [
                {"fr_id": "FR-01", "requires": [], "parallel_with": []},
                {"fr_id": "FR-02", "requires": ["FR-01"], "parallel_with": []},
                {"fr_id": "FR-03", "requires": ["FR-01", "FR-02"], "parallel_with": []},
            ],
        },
    }


class TestDecomposeFromSpecYaml:
    def test_basic_decomposition(self, tmp_path: Path):
        spec_path = _write_spec_yaml(tmp_path, _make_spec_yaml_data())
        result = decompose_from_spec_yaml(spec_path)

        assert len(result.modules) == 3
        assert result.modules[0].fr_id == "FR-01"
        assert result.modules[1].fr_id == "FR-02"
        assert result.modules[2].fr_id == "FR-03"

    def test_module_names_derived_from_fr_ids(self, tmp_path: Path):
        spec_path = _write_spec_yaml(tmp_path, _make_spec_yaml_data())
        result = decompose_from_spec_yaml(spec_path)

        assert result.modules[0].module_name == "fr01"
        assert result.modules[1].module_name == "fr02"
        assert result.modules[2].module_name == "fr03"

    def test_acs_assigned_to_modules(self, tmp_path: Path):
        spec_path = _write_spec_yaml(tmp_path, _make_spec_yaml_data())
        result = decompose_from_spec_yaml(spec_path)

        assert result.modules[0].ac_ids == ["AC-01", "AC-02"]
        assert result.modules[1].ac_ids == ["AC-03", "AC-04"]
        assert result.modules[2].ac_ids == ["AC-04", "AC-05"]

    def test_dependencies_mapped(self, tmp_path: Path):
        spec_path = _write_spec_yaml(tmp_path, _make_spec_yaml_data())
        result = decompose_from_spec_yaml(spec_path)

        assert result.modules[0].dependency_names == []
        assert result.modules[1].dependency_names == ["fr01"]
        assert result.modules[2].dependency_names == ["fr01", "fr02"]

    def test_glossary_extracted(self, tmp_path: Path):
        spec_path = _write_spec_yaml(tmp_path, _make_spec_yaml_data())
        result = decompose_from_spec_yaml(spec_path)

        assert result.glossary == {"widget": "A unit of work"}
        assert result.modules[0].glossary == {"widget": "A unit of work"}

    def test_source_hash_computed(self, tmp_path: Path):
        spec_path = _write_spec_yaml(tmp_path, _make_spec_yaml_data())
        result = decompose_from_spec_yaml(spec_path)

        assert len(result.source_hash) == 16

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            decompose_from_spec_yaml(Path("/nonexistent/spec.yaml"))

    def test_empty_spec_produces_no_modules(self, tmp_path: Path):
        spec_path = _write_spec_yaml(tmp_path, {"meta": {}, "functional_requirements": []})
        result = decompose_from_spec_yaml(spec_path)

        assert len(result.modules) == 0

    def test_fr_with_no_acs(self, tmp_path: Path):
        data = _make_spec_yaml_data()
        data["acceptance_criteria"] = []
        spec_path = _write_spec_yaml(tmp_path, data)
        result = decompose_from_spec_yaml(spec_path)

        assert result.modules[0].ac_ids == []
        assert result.modules[0].ac_entries == []


class TestDecomposeFromSpecMd:
    def test_basic_md_decomposition(self, tmp_path: Path):
        spec_md = textwrap.dedent("""\
            # Specification: Test Spec

            ## 2. Glossary

            | Term | Definition |
            |---|---|
            | widget | A unit of work |
            | cycle | One iteration |

            ## 5. Functional Requirements

            - FR-01 **[MVP]**: The system loads config from file.
            - FR-02 **[MVP]**: The system processes items sequentially.
            - FR-03 **[MVP]**: The system outputs results as JSON.

            ## 11. Acceptance Criteria

            - AC-01 [FR-01]: Config loads with defaults
            - AC-02 [FR-01]: Config validates fields
            - AC-03 [FR-02]: Items are processed in order
            - AC-04 [FR-03]: Output is valid JSON

            ## 12. Work Decomposition

            ### Implementation Phasing

            - FR-01: no prerequisites
            - FR-02: requires FR-01
            - FR-03: requires FR-01, FR-02
        """)
        spec_path = tmp_path / "spec.md"
        spec_path.write_text(spec_md)

        result = decompose_from_spec_md(spec_path)

        assert len(result.modules) == 3
        assert result.modules[0].fr_id == "FR-01"
        assert result.modules[1].ac_ids == ["AC-03"]
        assert result.modules[2].dependency_names == ["fr01", "fr02"]
        assert result.glossary == {"widget": "A unit of work", "cycle": "One iteration"}

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            decompose_from_spec_md(Path("/nonexistent/spec.md"))

    def test_no_matching_frs_produces_empty(self, tmp_path: Path):
        spec_path = tmp_path / "spec.md"
        spec_path.write_text("# No content\n")
        result = decompose_from_spec_md(spec_path)

        assert len(result.modules) == 0


class TestWriteFixtureFiles:
    def test_writes_per_module_files(self, tmp_path: Path):
        spec_path = _write_spec_yaml(tmp_path / "src", _make_spec_yaml_data())
        result = decompose_from_spec_yaml(spec_path)

        output_dir = tmp_path / "fixtures"
        written = write_fixture_files(result, output_dir)

        assert len(written) == 3
        assert all(p.exists() for p in written)
        names = sorted(p.name for p in written)
        assert names == ["wi_fr01.md", "wi_fr02.md", "wi_fr03.md"]

    def test_fixture_contains_dependencies_section(self, tmp_path: Path):
        spec_path = _write_spec_yaml(tmp_path / "src", _make_spec_yaml_data())
        result = decompose_from_spec_yaml(spec_path)

        output_dir = tmp_path / "fixtures"
        write_fixture_files(result, output_dir)

        fr02_content = (output_dir / "wi_fr02.md").read_text()
        assert "## Dependencies" in fr02_content
        assert "`interface_ref`: `fr01`" in fr02_content

    def test_leaf_module_has_none_deps(self, tmp_path: Path):
        spec_path = _write_spec_yaml(tmp_path / "src", _make_spec_yaml_data())
        result = decompose_from_spec_yaml(spec_path)

        output_dir = tmp_path / "fixtures"
        write_fixture_files(result, output_dir)

        fr01_content = (output_dir / "wi_fr01.md").read_text()
        assert "## Dependencies" in fr01_content
        assert "None." in fr01_content

    def test_fixture_contains_ac_headings(self, tmp_path: Path):
        spec_path = _write_spec_yaml(tmp_path / "src", _make_spec_yaml_data())
        result = decompose_from_spec_yaml(spec_path)

        output_dir = tmp_path / "fixtures"
        write_fixture_files(result, output_dir)

        fr01_content = (output_dir / "wi_fr01.md").read_text()
        assert "## AC-01" in fr01_content
        assert "## AC-02" in fr01_content
        assert "Config loads" in fr01_content

    def test_fixture_contains_glossary(self, tmp_path: Path):
        spec_path = _write_spec_yaml(tmp_path / "src", _make_spec_yaml_data())
        result = decompose_from_spec_yaml(spec_path)

        output_dir = tmp_path / "fixtures"
        write_fixture_files(result, output_dir)

        fr01_content = (output_dir / "wi_fr01.md").read_text()
        assert "## Glossary" in fr01_content
        assert "**widget**" in fr01_content

    def test_output_dir_created_if_missing(self, tmp_path: Path):
        spec_path = _write_spec_yaml(tmp_path / "src", _make_spec_yaml_data())
        result = decompose_from_spec_yaml(spec_path)

        output_dir = tmp_path / "nested" / "fixtures"
        written = write_fixture_files(result, output_dir)

        assert output_dir.exists()
        assert len(written) == 3


class TestRefurbWatcherRoundtrip:
    def test_refurb_watcher_spec_yaml_decomposition(self):
        spec_path = Path("tests/fixtures/refurb-watcher/spec.yaml")
        if not spec_path.exists():
            pytest.skip("refurb-watcher spec.yaml not found")

        result = decompose_from_spec_yaml(spec_path)

        assert len(result.modules) == 6
        module_names = [m.module_name for m in result.modules]
        assert "fr01" in module_names
        assert "fr06" in module_names

        fr01 = next(m for m in result.modules if m.fr_id == "FR-01")
        assert len(fr01.ac_entries) >= 1
        assert fr01.dependency_names == []

        fr06 = next(m for m in result.modules if m.fr_id == "FR-06")
        assert len(fr06.dependency_names) >= 1

    def test_refurb_watcher_fixture_writes_valid_spec(self, tmp_path: Path):
        spec_path = Path("tests/fixtures/refurb-watcher/spec.yaml")
        if not spec_path.exists():
            pytest.skip("refurb-watcher spec.yaml not found")

        result = decompose_from_spec_yaml(spec_path)
        output_dir = tmp_path / "fixtures"
        write_fixture_files(result, output_dir)

        for module in result.modules:
            fixture = output_dir / f"wi_{module.module_name}.md"
            assert fixture.exists()
            content = fixture.read_text()
            assert "# Interface Specification:" in content
            assert "## Dependencies" in content

    def test_refurb_watcher_md_decomposition(self):
        spec_path = Path("tests/fixtures/refurb-watcher/spec.md")
        if not spec_path.exists():
            pytest.skip("refurb-watcher spec.md not found")

        result = decompose_from_spec_md(spec_path)

        assert len(result.modules) == 6
        fr_ids = [m.fr_id for m in result.modules]
        assert "FR-01" in fr_ids
        assert "FR-06" in fr_ids
