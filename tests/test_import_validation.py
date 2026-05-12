from __future__ import annotations

from unittest.mock import patch

from factory.constants import GATE_NAME_INNER_IMPORT_SYMBOLS
from factory.context import PromptContext, render_prompt
from factory.gate import extract_exports
from factory.pre_gate import PreGateDeps, validate_artifact_imports


class TestImportValidationHappyPath:
    def test_import_validation_happy_path(self, tmp_path):
        artifact = tmp_path / "mod.py"
        artifact.write_text("from certificate_model import Certificate, CertStatus\n")
        export_map = {"certificate_model": {"Certificate", "CertStatus", "CertChain"}}
        ok, diags, skipped = validate_artifact_imports(artifact, export_map)
        assert ok is True
        assert diags == []
        assert skipped == {}


class TestImportValidationUnknownSymbol:
    def test_import_validation_unknown_symbol_single(self, tmp_path):
        artifact = tmp_path / "mod.py"
        artifact.write_text("from certificate_model import parse_certificate\n")
        export_map = {"certificate_model": {"Certificate", "CertStatus", "verify"}}
        ok, diags, _skipped = validate_artifact_imports(artifact, export_map)
        assert ok is False
        assert len(diags) == 2
        assert "parse_certificate" in diags[0]
        assert ":1:" in diags[0]
        assert "available in certificate_model" in diags[1]
        assert "Certificate" in diags[1]
        assert "CertStatus" in diags[1]
        assert "verify" in diags[1]

    def test_import_validation_unknown_symbol_multiple(self, tmp_path):
        artifact = tmp_path / "mod.py"
        artifact.write_text(
            "from certificate_model import bad1, bad2\nfrom cert_parser import bad3\n"
        )
        export_map = {
            "certificate_model": {"Certificate"},
            "cert_parser": {"parse_pem", "parse_der"},
        }
        ok, diags, _skipped = validate_artifact_imports(artifact, export_map)
        assert ok is False
        assert len(diags) == 4
        cert_model_lines = [d for d in diags if "certificate_model" in d and "unknown" in d]
        cert_parser_lines = [d for d in diags if "cert_parser" in d and "unknown" in d]
        assert len(cert_model_lines) == 1
        assert len(cert_parser_lines) == 1
        assert "bad1" in cert_model_lines[0]
        assert "bad2" in cert_model_lines[0]
        assert "bad3" in cert_parser_lines[0]

    def test_import_validation_grouped_on_one_line(self, tmp_path):
        artifact = tmp_path / "mod.py"
        artifact.write_text("from mymod import good, bad1, bad2\n")
        export_map = {"mymod": {"good", "other"}}
        ok, diags, _skipped = validate_artifact_imports(artifact, export_map)
        assert ok is False
        unknown_line = next(d for d in diags if "unknown symbols" in d)
        assert "bad1" in unknown_line
        assert "bad2" in unknown_line
        assert "good" not in unknown_line


class TestImportValidationSkipPatterns:
    def test_import_validation_skips_unknown_module(self, tmp_path):
        artifact = tmp_path / "mod.py"
        artifact.write_text("from third_party import x\n")
        export_map = {"certificate_model": {"Certificate"}}
        ok, diags, _skipped = validate_artifact_imports(artifact, export_map)
        assert ok is True
        assert diags == []

    def test_import_validation_skips_submodule_import(self, tmp_path):
        artifact = tmp_path / "mod.py"
        artifact.write_text("from a.b import c\n")
        export_map = {"a": {"x"}}
        ok, _diags, skipped = validate_artifact_imports(artifact, export_map)
        assert ok is True
        assert skipped.get("submodule_dotted", 0) >= 1

    def test_import_validation_skips_type_checking_block(self, tmp_path):
        artifact = tmp_path / "mod.py"
        artifact.write_text(
            "from typing import TYPE_CHECKING\nif TYPE_CHECKING:\n    from mymod import BadSymbol\n"
        )
        export_map = {"mymod": {"GoodSymbol"}}
        ok, _diags, skipped = validate_artifact_imports(artifact, export_map)
        assert ok is True
        assert skipped.get("type_checking_block", 0) >= 1

    def test_import_validation_skips_star_import(self, tmp_path):
        artifact = tmp_path / "mod.py"
        artifact.write_text("from mymod import *\n")
        export_map = {"mymod": {"a", "b"}}
        ok, _diags, skipped = validate_artifact_imports(artifact, export_map)
        assert ok is True
        assert skipped.get("star", 0) >= 1

    def test_import_validation_skips_relative_import(self, tmp_path):
        artifact = tmp_path / "mod.py"
        artifact.write_text("from . import x\n")
        export_map = {}
        ok, _diags, skipped = validate_artifact_imports(artifact, export_map)
        assert ok is True
        assert skipped.get("relative", 0) >= 1


class TestExtractExports:
    def test_extract_exports_strips_type_prefixes(self):
        pyi = (
            "from dataclasses import dataclass\n"
            "from enum import Enum\n"
            "\n"
            "def parse_pem(data: bytes) -> str: ...\n"
            "\n"
            "@dataclass(frozen=True)\n"
            "class Certificate:\n"
            "    name: str\n"
            "\n"
            "CertFormat = str | bytes\n"
        )
        exports = extract_exports(pyi)
        assert "parse_pem" in exports
        assert "Certificate" in exports
        assert "CertFormat" in exports
        for name in exports:
            assert not name.startswith("fn:")
            assert not name.startswith("class:")
            assert not name.startswith("type_alias:")
            assert not name.startswith("enum_member:")
            assert not name.startswith("ac_ref:")

    def test_extract_exports_enum_members_collapse_to_class(self):
        pyi = "from enum import Enum\n\nclass Status(Enum):\n    OK = 1\n    ERR = 2\n"
        exports = extract_exports(pyi)
        assert exports == {"Status"}
        assert "Status.OK" not in exports
        assert "Status.ERR" not in exports


class TestManifestInPrompt:
    def test_manifest_includes_stub_only_tag(self):
        ctx = PromptContext(
            work_item_id="wi-1",
            role="implementer",
            spec_section="content",
            ac_ids=["AC-01"],
            glossary={},
            prior_failures=[],
            prompt_template="",
            context_hash="abc",
            prompt_template_hash="",
            extra_artifacts={},
            stub_only_deps=["cert_parser"],
            export_map={"cert_parser": {"parse_pem", "parse_der"}},
        )
        prompt = render_prompt(ctx)
        assert "available_dependency_imports" in prompt
        assert "cert_parser (stub-only)" in prompt
        assert "parse_pem" in prompt
        assert "parse_der" in prompt

    def test_manifest_excludes_stub_only_tag_for_runtime_module(self):
        ctx = PromptContext(
            work_item_id="wi-1",
            role="implementer",
            spec_section="content",
            ac_ids=["AC-01"],
            glossary={},
            prior_failures=[],
            prompt_template="",
            context_hash="abc",
            prompt_template_hash="",
            extra_artifacts={},
            stub_only_deps=["other_module"],
            export_map={"cert_model": {"Certificate"}, "other_module": {"X"}},
        )
        prompt = render_prompt(ctx)
        assert "cert_model" in prompt
        cert_model_lines = [
            ln for ln in prompt.splitlines() if "cert_model" in ln and "available" not in ln.lower()
        ]
        for line in cert_model_lines:
            if line.strip().startswith("- cert_model"):
                assert "(stub-only)" not in line


class TestPreGateCascade:
    def test_pregate_cascade_import_symbols_first(self, tmp_path):
        artifact = tmp_path / "mod.py"
        artifact.write_text("from mymod import nonexistent_symbol\n")
        interface_pyi = tmp_path / "interface.pyi"
        interface_pyi.write_text("def hello() -> str: ...\n")
        export_map = {"mymod": {"real_thing"}}
        from factory.pre_gate import pre_gate_implementation

        result = pre_gate_implementation(
            artifact,
            interface_pyi_path=interface_pyi,
            export_map=export_map,
        )
        assert result.imports_symbols_passed is False
        assert result.mypy_passed is True
        assert result.passed is False

        from factory.runner import _run_pre_gate

        deps = PreGateDeps(
            interface_pyi_path=interface_pyi,
            dep_paths=None,
            dep_spec_paths=None,
            python_executable=None,
            test_suite_path=None,
        )
        result2 = _run_pre_gate(
            "implementer",
            artifact,
            deps,
            export_map=export_map,
        )
        assert result2.imports_symbols_passed is False
        assert GATE_NAME_INNER_IMPORT_SYMBOLS == "inner_import_symbols"


class TestExportMapCaching:
    def test_export_map_cached_per_work_item(self, tmp_path):
        dep_pyi = tmp_path / "mymod.pyi"
        dep_pyi.write_text("def foo() -> str: ...\n")
        dep_paths = [("mymod", dep_pyi)]

        with patch("factory.gate.extract_exports", wraps=extract_exports) as mock_extract:
            from factory.runner import _build_export_map

            _build_export_map(dep_paths)
            call_count_1 = mock_extract.call_count

            _build_export_map(dep_paths)
            call_count_2 = mock_extract.call_count
            assert call_count_2 == call_count_1 + 1
