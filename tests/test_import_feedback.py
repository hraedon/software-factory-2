from __future__ import annotations

from factory.context import PromptContext, render_prompt
from factory.pre_gate import (
    _IMPORT_FEEDBACK_KIND_DOTTED_SUBMODULE,
    _IMPORT_FEEDBACK_KIND_OTHER,
    _IMPORT_FEEDBACK_KIND_WRONG_MODULE_NAME,
    _is_safe_from_feedback,
    _parse_import_failure,
    _parse_requirements_packages,
    _run_import_check,
)


class TestParseImportFailureDottedSubmodule:
    def test_dotted_submodule_no_module_found(self):
        stderr = (
            "Traceback (most recent call last):\n"
            '  File "<string>", line 1, in <module>\n'
            "ModuleNotFoundError: No module named "
            "'cryptography.hazmat.primitives'"
        )
        kind, msg = _parse_import_failure(
            stderr,
            available_modules=["cryptography", "certificate_model"],
        )
        assert kind == _IMPORT_FEEDBACK_KIND_DOTTED_SUBMODULE
        assert "dotted submodule" in msg
        assert "cryptography.hazmat.primitives" in msg
        assert "flat modules" in msg
        assert "cryptography" in msg

    def test_dotted_submodule_triple_dotted(self):
        stderr = "ModuleNotFoundError: No module named 'a.b.c'"
        kind, msg = _parse_import_failure(stderr, available_modules=["a"])
        assert kind == _IMPORT_FEEDBACK_KIND_DOTTED_SUBMODULE
        assert "from a import" in msg

    def test_dotted_submodule_without_available_modules(self):
        # Use a non-stdlib package to test the dotted-submodule path without suppression
        stderr = "ModuleNotFoundError: No module named 'cryptography.hazmat'"
        kind, msg = _parse_import_failure(stderr, available_modules=None)
        assert kind == _IMPORT_FEEDBACK_KIND_DOTTED_SUBMODULE
        assert "dotted submodule" in msg
        assert "Available flat modules" not in msg

    def test_dotted_import_error(self):
        stderr = (
            "ImportError: cannot import name 'serialization' from 'cryptography.hazmat.primitives'"
        )
        kind, msg = _parse_import_failure(stderr)
        assert kind == _IMPORT_FEEDBACK_KIND_DOTTED_SUBMODULE
        assert "dotted submodule" in msg


class TestParseImportFailureWrongModuleName:
    def test_wrong_module_name_with_suggestion(self):
        stderr = "ModuleNotFoundError: No module named 'cert_model'"
        kind, msg = _parse_import_failure(
            stderr,
            available_modules=["certificate_model", "database_layer"],
        )
        assert kind == _IMPORT_FEEDBACK_KIND_WRONG_MODULE_NAME
        assert "cert_model" in msg
        assert "certificate_model" in msg
        assert "Did you mean" in msg

    def test_wrong_module_name_no_close_match(self):
        stderr = "ModuleNotFoundError: No module named 'xyzzy_totally_wrong'"
        kind, msg = _parse_import_failure(
            stderr,
            available_modules=["certificate_model", "database_layer"],
        )
        assert kind == _IMPORT_FEEDBACK_KIND_WRONG_MODULE_NAME
        assert "Did you mean" not in msg

    def test_wrong_module_name_with_line_info(self):
        stderr = "ModuleNotFoundError: No module named 'cert_model'"
        artifact_lines = [
            "import os",
            "from cert_model import Certificate",
        ]
        kind, msg = _parse_import_failure(
            stderr,
            artifact_lines=artifact_lines,
            available_modules=["certificate_model"],
        )
        assert kind == _IMPORT_FEEDBACK_KIND_WRONG_MODULE_NAME
        assert "line 2" in msg

    def test_wrong_module_name_without_line_info(self):
        stderr = "ModuleNotFoundError: No module named 'cert_model'"
        kind, msg = _parse_import_failure(
            stderr,
            artifact_lines=None,
            available_modules=["certificate_model"],
        )
        assert kind == _IMPORT_FEEDBACK_KIND_WRONG_MODULE_NAME
        assert "line" not in msg


class TestParseImportFailureOther:
    def test_generic_syntax_error(self):
        stderr = (
            '  File "<string>", line 1\n    import ==\n          ^\nSyntaxError: invalid syntax'
        )
        kind, _msg = _parse_import_failure(stderr)
        assert kind == _IMPORT_FEEDBACK_KIND_OTHER

    def test_empty_stderr(self):
        kind, _msg = _parse_import_failure("")
        assert kind == _IMPORT_FEEDBACK_KIND_OTHER

    def test_unrecognized_error_pattern(self):
        kind, _msg = _parse_import_failure("Something completely unexpected happened")
        assert kind == _IMPORT_FEEDBACK_KIND_OTHER


class TestParseImportFailureBudget:
    def test_feedback_under_500_chars(self):
        stderr = "ModuleNotFoundError: No module named 'very.long.dotted.path.that.goes.on.and.on'"
        with_many_modules = [f"module_{i}" for i in range(100)]
        kind, msg = _parse_import_failure(stderr, available_modules=with_many_modules)
        assert kind == _IMPORT_FEEDBACK_KIND_DOTTED_SUBMODULE
        assert len(msg) <= 500


class TestRunImportCheckFeedback:
    def test_import_check_returns_feedback_on_dotted_submodule(self, tmp_path):
        artifact = tmp_path / "my_module.py"
        artifact.write_text("from cryptography.hazmat.primitives import serialization\n")
        dep_path = tmp_path / "cryptography.pyi"
        dep_path.write_text("def encrypt(): ...\ndef decrypt(): ...\n")
        result = _run_import_check(
            artifact,
            dependency_pyi_paths=[("cryptography", dep_path)],
        )
        assert result["passed"] is False
        assert result.get("import_feedback_kind") == _IMPORT_FEEDBACK_KIND_DOTTED_SUBMODULE
        assert "dotted submodule" in result.get("import_feedback", "")

    def test_import_check_returns_feedback_on_wrong_name(self, tmp_path):
        dep_path = tmp_path / "certificate_model.pyi"
        dep_path.write_text("class Certificate: ...\n")
        artifact = tmp_path / "my_module.py"
        artifact.write_text("from cert_model import Certificate\n")
        result = _run_import_check(
            artifact,
            dependency_pyi_paths=[("certificate_model", dep_path)],
        )
        assert result["passed"] is False
        feedback_kind = result.get("import_feedback_kind", "")
        assert feedback_kind == _IMPORT_FEEDBACK_KIND_WRONG_MODULE_NAME
        assert "certificate_model" in result.get("import_feedback", "")

    def test_import_check_returns_other_on_syntax_error(self, tmp_path):
        artifact = tmp_path / "my_module.py"
        artifact.write_text("this is not valid python ===\n")
        result = _run_import_check(artifact)
        assert result["passed"] is False
        assert result.get("import_feedback_kind", "") == (_IMPORT_FEEDBACK_KIND_OTHER)

    def test_import_check_no_feedback_on_success(self, tmp_path):
        artifact = tmp_path / "my_module.py"
        artifact.write_text("x = 1\n")
        result = _run_import_check(artifact)
        assert result["passed"] is True
        assert result.get("import_feedback_kind", "") == ""
        assert result.get("import_feedback", "") == ""


class TestRenderPromptImportFeedback:
    def test_import_feedback_appears_in_rendered_prompt(self):
        ctx = PromptContext(
            work_item_id="wi-1",
            role="interface_architect",
            spec_section="section",
            ac_ids=["AC-01"],
            glossary={},
            prior_failures=[],
            prompt_template="template",
            context_hash="abc",
            prompt_template_hash="",
            extra_artifacts={},
            stub_only_deps=[],
            import_feedback=(
                "Import resolution failed: 'cert_model' not found.\n"
                "Available modules: certificate_model\n"
                "Did you mean: certificate_model?"
            ),
        )
        rendered = render_prompt(ctx)
        assert "## import_resolution_feedback" in rendered
        assert "cert_model" in rendered
        assert "certificate_model" in rendered

    def test_import_feedback_absent_when_empty(self):
        ctx = PromptContext(
            work_item_id="wi-1",
            role="interface_architect",
            spec_section="section",
            ac_ids=["AC-01"],
            glossary={},
            prior_failures=[],
            prompt_template="template",
            context_hash="abc",
            prompt_template_hash="",
            extra_artifacts={},
            stub_only_deps=[],
            import_feedback="",
        )
        rendered = render_prompt(ctx)
        assert "import_resolution_feedback" not in rendered


class TestPreGateInterfaceSpecFeedback:
    def test_import_error_includes_feedback_kind(self, tmp_path):
        from factory.pre_gate import pre_gate_interface_spec

        dep_pyi = tmp_path / "certificate_model.pyi"
        dep_pyi.write_text("class Certificate:\n    subject: str\n")
        artifact = tmp_path / "spec.pyi"
        artifact.write_text(
            "from cert_model import Certificate\nclass Scanner:\n    cert: Certificate\n"
        )
        result = pre_gate_interface_spec(
            artifact,
            dependency_pyi_paths=[("certificate_model", dep_pyi)],
        )
        assert not result.passed
        assert result.import_feedback_kind == (_IMPORT_FEEDBACK_KIND_WRONG_MODULE_NAME)
        assert "certificate_model" in result.import_feedback

    def test_dotted_import_includes_feedback(self, tmp_path):
        from factory.pre_gate import pre_gate_interface_spec

        dep_pyi = tmp_path / "cryptography.pyi"
        dep_pyi.write_text("def encrypt(): ...\n")
        artifact = tmp_path / "spec.pyi"
        artifact.write_text(
            "from cryptography.hazmat.primitives import serialization\n"
            "class Scanner:\n"
            "    x: serialization\n"
        )
        result = pre_gate_interface_spec(
            artifact,
            dependency_pyi_paths=[("cryptography", dep_pyi)],
        )
        assert not result.passed
        assert result.import_feedback_kind == (_IMPORT_FEEDBACK_KIND_DOTTED_SUBMODULE)
        result = pre_gate_interface_spec(
            artifact,
            dependency_pyi_paths=[("cryptography", dep_pyi)],
        )
        assert not result.passed
        assert result.import_feedback_kind == (_IMPORT_FEEDBACK_KIND_DOTTED_SUBMODULE)


# ---------------------------------------------------------------------------
# BC-183: False-positive suppression for stdlib and known third-party imports
# ---------------------------------------------------------------------------


class TestParseRequirementsPackages:
    def test_extracts_plain_package_name(self, tmp_path):
        req = tmp_path / "requirements.txt"
        req.write_text("fastapi\n")
        assert "fastapi" in _parse_requirements_packages(req)

    def test_strips_version_specifier(self, tmp_path):
        req = tmp_path / "requirements.txt"
        req.write_text("fastapi>=0.100.0\n")
        assert "fastapi" in _parse_requirements_packages(req)

    def test_strips_extras(self, tmp_path):
        req = tmp_path / "requirements.txt"
        req.write_text("fastapi[all]>=0.100\n")
        assert "fastapi" in _parse_requirements_packages(req)

    def test_normalises_dashes_to_underscores(self, tmp_path):
        req = tmp_path / "requirements.txt"
        req.write_text("some-package>=1.0\n")
        pkgs = _parse_requirements_packages(req)
        assert "some_package" in pkgs

    def test_skips_blank_lines_and_comments(self, tmp_path):
        req = tmp_path / "requirements.txt"
        req.write_text("# comment\n\nfastapi>=0.100\n")
        pkgs = _parse_requirements_packages(req)
        assert "fastapi" in pkgs
        assert "" not in pkgs

    def test_returns_empty_frozenset_when_path_is_none(self):
        assert _parse_requirements_packages(None) == frozenset()

    def test_returns_empty_frozenset_when_file_missing(self, tmp_path):
        assert _parse_requirements_packages(tmp_path / "nonexistent.txt") == frozenset()


class TestIsSafeFromFeedback:
    def test_stdlib_top_level_is_safe(self):
        assert _is_safe_from_feedback("collections", frozenset())
        assert _is_safe_from_feedback("unittest", frozenset())
        assert _is_safe_from_feedback("os", frozenset())

    def test_known_package_is_safe(self):
        known = frozenset(["fastapi", "pydantic"])
        assert _is_safe_from_feedback("fastapi", known)
        assert _is_safe_from_feedback("pydantic", known)

    def test_unknown_non_stdlib_is_not_safe(self):
        assert not _is_safe_from_feedback("cert_model_typo", frozenset())
        assert not _is_safe_from_feedback("xyzzy_nonexistent", frozenset())

    def test_stdlib_check_is_case_sensitive_to_match_sys_stdlib_module_names(self):
        # sys.stdlib_module_names uses lower-case canonical names
        assert _is_safe_from_feedback("os", frozenset())
        assert not _is_safe_from_feedback("cert_model_typo", frozenset())


class TestParseImportFailureStdlibSuppression:
    """AC-1 and AC-2: stdlib submodule imports do not produce dotted_submodule feedback."""

    def test_collections_abc_returns_other(self):
        # AC-1: from collections.abc import Mapping
        stderr = "ModuleNotFoundError: No module named 'collections.abc'"
        kind, _ = _parse_import_failure(stderr)
        assert kind == _IMPORT_FEEDBACK_KIND_OTHER

    def test_unittest_mock_returns_other(self):
        # AC-2: from unittest.mock import MagicMock
        stderr = "ModuleNotFoundError: No module named 'unittest.mock'"
        kind, _ = _parse_import_failure(stderr)
        assert kind == _IMPORT_FEEDBACK_KIND_OTHER

    def test_os_path_returns_other(self):
        stderr = "ModuleNotFoundError: No module named 'os.path'"
        kind, _ = _parse_import_failure(stderr)
        assert kind == _IMPORT_FEEDBACK_KIND_OTHER

    def test_import_error_from_stdlib_submodule_returns_other(self):
        stderr = "ImportError: cannot import name 'Mapping' from 'collections.abc'"
        kind, _ = _parse_import_failure(stderr)
        assert kind == _IMPORT_FEEDBACK_KIND_OTHER


class TestParseImportFailureKnownPackageSuppression:
    """AC-3 and AC-4: known third-party packages suppressed; true positives still caught."""

    def test_fastapi_wrong_module_suppressed_with_known_packages(self):
        # AC-3: fastapi in requirements.txt should not produce wrong_module_name
        stderr = "ModuleNotFoundError: No module named 'fastapi'"
        known = frozenset(["fastapi"])
        kind, _ = _parse_import_failure(stderr, known_packages=known)
        assert kind == _IMPORT_FEEDBACK_KIND_OTHER

    def test_fastapi_testclient_dotted_suppressed_with_known_packages(self):
        # AC-3: fastapi.testclient submodule suppressed when fastapi in requirements.txt
        stderr = "ModuleNotFoundError: No module named 'fastapi.testclient'"
        known = frozenset(["fastapi"])
        kind, _ = _parse_import_failure(stderr, known_packages=known)
        assert kind == _IMPORT_FEEDBACK_KIND_OTHER

    def test_fastapi_responses_dotted_suppressed_with_known_packages(self):
        # AC-3: fastapi.responses submodule suppressed when fastapi in requirements.txt
        stderr = "ModuleNotFoundError: No module named 'fastapi.responses'"
        known = frozenset(["fastapi"])
        kind, _ = _parse_import_failure(stderr, known_packages=known)
        assert kind == _IMPORT_FEEDBACK_KIND_OTHER

    def test_genuinely_wrong_import_still_produces_feedback(self):
        # AC-4: typo'd module not in stdlib/requirements still produces wrong_module_name
        stderr = "ModuleNotFoundError: No module named 'cert_model_typo'"
        kind, _ = _parse_import_failure(
            stderr,
            available_modules=["certificate_model"],
            known_packages=frozenset(),
        )
        assert kind == _IMPORT_FEEDBACK_KIND_WRONG_MODULE_NAME

    def test_genuinely_wrong_dotted_import_still_produces_feedback(self):
        # AC-4: dotted import for non-stdlib, non-requirements package still produces feedback
        stderr = "ModuleNotFoundError: No module named 'cert_model_typo.sub'"
        kind, _ = _parse_import_failure(
            stderr,
            available_modules=["certificate_model"],
            known_packages=frozenset(["certificate_model"]),
        )
        # cert_model_typo is not stdlib and not in known_packages -> dotted_submodule
        assert kind == _IMPORT_FEEDBACK_KIND_DOTTED_SUBMODULE


class TestRunImportCheckWithRequirementsPath:
    """Integration tests for requirements_path threading through _run_import_check."""

    def test_stdlib_submodule_does_not_produce_dotted_feedback(self, tmp_path):
        artifact = tmp_path / "my_module.py"
        artifact.write_text("from collections.abc import Mapping\n\nMapping\n")
        # No dep pyis, no requirements.txt; stdlib check alone suppresses feedback
        result = _run_import_check(artifact)
        if not result["passed"]:
            assert result.get("import_feedback_kind") == _IMPORT_FEEDBACK_KIND_OTHER

    def test_known_package_from_requirements_does_not_produce_wrong_module_feedback(self, tmp_path):
        req = tmp_path / "requirements.txt"
        req.write_text("fastapi>=0.100\n")
        artifact = tmp_path / "my_module.py"
        artifact.write_text("from fastapi import FastAPI\n\nFastAPI\n")
        result = _run_import_check(artifact, requirements_path=req)
        if not result["passed"]:
            assert result.get("import_feedback_kind") == _IMPORT_FEEDBACK_KIND_OTHER
