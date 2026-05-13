from __future__ import annotations

from factory.context import PromptContext, render_prompt
from factory.pre_gate import (
    _IMPORT_FEEDBACK_KIND_DOTTED_SUBMODULE,
    _IMPORT_FEEDBACK_KIND_OTHER,
    _IMPORT_FEEDBACK_KIND_WRONG_MODULE_NAME,
    _parse_import_failure,
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
        stderr = "ModuleNotFoundError: No module named 'os.path'"
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
