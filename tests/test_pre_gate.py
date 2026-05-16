from __future__ import annotations

from pathlib import Path

from factory.pre_gate import (
    PreGateDeps,
    copy_dependency_pyis,
    pre_gate_implementation,
    pre_gate_integrator,
    pre_gate_interface_spec,
    pre_gate_outcome_verifier,
    pre_gate_test_suite,
)


class TestPreGateImplementation:
    def test_passes_on_clean_artifact(self, tmp_path):
        artifact = tmp_path / "interface.py"
        artifact.write_text("def hello() -> str:\n    return 'hello'\n")
        interface_pyi = tmp_path / "interface.pyi"
        interface_pyi.write_text("def hello() -> str: ...\n")
        result = pre_gate_implementation(artifact, interface_pyi_path=interface_pyi)
        assert result.passed
        assert result.mypy_passed
        assert result.ruff_passed
        assert result.pytest_passed
        assert result.diagnostics == []

    def test_fails_on_mypy_error(self, tmp_path):
        artifact = tmp_path / "interface.py"
        artifact.write_text("def hello() -> str:\n    pass\n")
        interface_pyi = tmp_path / "interface.pyi"
        interface_pyi.write_text("def hello() -> str: ...\n")
        result = pre_gate_implementation(artifact, interface_pyi_path=interface_pyi)
        assert not result.passed
        assert not result.mypy_passed

    def test_auto_fixes_ruff_errors(self, tmp_path):
        artifact = tmp_path / "interface.py"
        artifact.write_text("def hello() -> str:\n    x=1+2\n    return 'hello'\n")
        interface_pyi = tmp_path / "interface.pyi"
        interface_pyi.write_text("def hello() -> str: ...\n")
        result = pre_gate_implementation(artifact, interface_pyi_path=interface_pyi)
        assert result.passed
        assert result.ruff_passed

    def test_skips_mypy_without_interface(self, tmp_path):
        artifact = tmp_path / "interface.py"
        artifact.write_text("def hello() -> str:\n    return 'hello'\n")
        result = pre_gate_implementation(artifact, interface_pyi_path=None)
        assert result.passed
        assert result.mypy_passed
        assert result.ruff_passed

    def test_passes_with_dependency(self, tmp_path):
        artifact = tmp_path / "interface.py"
        artifact.write_text(
            "from certificate_model import Certificate, "
            "parse_certificate\n"
            "def hello() -> Certificate | None:\n"
            "    return None\n"
        )
        interface_pyi = tmp_path / "interface.pyi"
        interface_pyi.write_text(
            "from certificate_model import Certificate, "
            "parse_certificate\n"
            "def hello() -> Certificate | None: ...\n"
        )
        dep_pyi = tmp_path / "dep_certificate_model.pyi"
        dep_pyi.write_text(
            "class Certificate:\n"
            "    subject: str\n"
            "    issuer: str\n\n"
            "class MalformedCertificateError:\n"
            "    message: str\n\n"
            "def parse_certificate("
            "der_bytes: bytes"
            ") -> Certificate | MalformedCertificateError: ...\n"
        )
        result = pre_gate_implementation(
            artifact,
            interface_pyi_path=interface_pyi,
            dependency_pyi_paths=[("certificate_model", dep_pyi)],
        )
        assert result.mypy_passed

    def test_pytest_passes_with_test_suite(self, tmp_path):
        impl = tmp_path / "impl.py"
        impl.write_text("def add(a: int, b: int) -> int:\n    return a + b\n")
        interface_pyi = tmp_path / "interface.pyi"
        interface_pyi.write_text("def add(a: int, b: int) -> int: ...\n")
        test_suite = tmp_path / "test_add.py"
        test_suite.write_text(
            "from interface import add\ndef test_add():\n    assert add(1, 2) == 3\n"
        )
        result = pre_gate_implementation(
            impl,
            interface_pyi_path=interface_pyi,
            test_suite_path=test_suite,
        )
        assert result.pytest_passed
        assert result.passed

    def test_pytest_failure_short_circuits_after_mypy_pass(self, tmp_path):
        artifact = tmp_path / "impl.py"
        artifact.write_text("def broken() -> str:\n    return 'wrong'\n")
        interface_pyi = tmp_path / "interface.pyi"
        interface_pyi.write_text("def broken() -> str: ...\n")
        test_suite = tmp_path / "test_broken.py"
        test_suite.write_text(
            "from interface import broken\n"
            "def test_broken():\n"
            "    assert broken() == 'unreachable'\n"
        )
        result = pre_gate_implementation(
            artifact,
            interface_pyi_path=interface_pyi,
            test_suite_path=test_suite,
        )
        assert not result.passed
        assert result.mypy_passed
        assert result.ruff_passed
        assert not result.pytest_passed

    def test_mypy_failure_skips_pytest(self, tmp_path):
        artifact = tmp_path / "interface.py"
        artifact.write_text("def hello() -> str:\n    pass\n")
        interface_pyi = tmp_path / "interface.pyi"
        interface_pyi.write_text("def hello() -> str: ...\n")
        test_suite = tmp_path / "test_hello.py"
        test_suite.write_text(
            "from interface import hello\n\ndef test_hello():\n    assert hello() == 'hi'\n"
        )
        result = pre_gate_implementation(
            artifact,
            interface_pyi_path=interface_pyi,
            test_suite_path=test_suite,
        )
        assert not result.passed
        assert not result.mypy_passed
        assert result.pytest_passed is True

    def test_pytest_skipped_when_no_test_suite(self, tmp_path):
        artifact = tmp_path / "interface.py"
        artifact.write_text("def hello() -> str:\n    return 'hello'\n")
        interface_pyi = tmp_path / "interface.pyi"
        interface_pyi.write_text("def hello() -> str: ...\n")
        result = pre_gate_implementation(
            artifact,
            interface_pyi_path=interface_pyi,
            test_suite_path=None,
        )
        assert result.passed
        assert result.pytest_passed

    def test_pre_gate_deps_named_tuple(self):
        deps = PreGateDeps(
            interface_pyi_path=None,
            dep_paths=None,
            python_executable=None,
            test_suite_path=None,
        )
        assert deps.interface_pyi_path is None
        assert deps.dep_paths is None
        assert deps.python_executable is None
        assert deps.test_suite_path is None

    def test_truncate_diagnostics(self):
        from factory.pre_gate import _truncate_diagnostics

        short = ["line 1", "line 2"]
        assert _truncate_diagnostics(short) == short
        long_line = "x" * 400
        result = _truncate_diagnostics([long_line])
        assert len(result[0]) < len(long_line)
        assert result[0].endswith("...")


class TestInnerGateToolNotFound:
    def test_ruff_missing_returns_failure(self, tmp_path):
        from unittest.mock import patch

        from factory.pre_gate import _run_ruff_fast

        artifact = tmp_path / "impl.py"
        artifact.write_text("x = 1\n")
        with patch("factory.pre_gate.subprocess.run", side_effect=FileNotFoundError("no ruff")):
            result = _run_ruff_fast(artifact, python_executable="/nonexistent/python")
        assert result["passed"] is False
        assert any("ruff invocation failed" in d for d in result["diagnostics"])

    def test_ruff_timeout_returns_failure(self, tmp_path):
        import subprocess
        from unittest.mock import patch

        from factory.pre_gate import _run_ruff_fast

        artifact = tmp_path / "impl.py"
        artifact.write_text("x = 1\n")
        with patch(
            "factory.pre_gate.subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="ruff", timeout=30),
        ):
            result = _run_ruff_fast(artifact)
        assert result["passed"] is False
        assert any("timed out" in d for d in result["diagnostics"])

    def test_mypy_missing_returns_failure(self, tmp_path):
        from factory.pre_gate import _run_mypy_fast

        artifact = tmp_path / "impl.py"
        artifact.write_text("x: int = 1\n")
        interface_pyi = tmp_path / "interface.pyi"
        interface_pyi.write_text("x: int\n")
        result = _run_mypy_fast(
            artifact,
            interface_pyi_path=interface_pyi,
            python_executable="/nonexistent/python",
        )
        assert not result["passed"]
        assert any("mypy" in d.lower() for d in result["diagnostics"])

    def test_pytest_missing_returns_failure(self, tmp_path):
        from factory.pre_gate import _run_pytest_fast

        artifact = tmp_path / "impl.py"
        artifact.write_text("def add(a, b): return a + b\n")
        test_suite = tmp_path / "test_add.py"
        test_suite.write_text("def test_add(): pass\n")
        result = _run_pytest_fast(
            artifact,
            test_suite_path=test_suite,
            python_executable="/nonexistent/python",
        )
        assert not result["passed"]
        assert any("pytest" in d.lower() or "failed" in d.lower() for d in result["diagnostics"])


class TestCopyDependencyPyis:
    def test_writes_module_name_files(self, tmp_path):
        import tempfile

        dep_pyi = tmp_path / "dep.pyi"
        dep_pyi.write_text("class Foo:\n    bar: str\n")
        with tempfile.TemporaryDirectory(prefix="sf2_test_") as tmpdir:
            copy_dependency_pyis(tmpdir, [("my_module", dep_pyi)])
            assert (Path(tmpdir) / "my_module.py").exists()
            assert (Path(tmpdir) / "my_module.pyi").exists()


class TestPreGateInterfaceSpec:
    def test_passes_on_clean_artifact(self, tmp_path):
        artifact = tmp_path / "artifact.pyi"
        artifact.write_text(
            "class Certificate:\n"
            "    subject: str\n"
            "    issuer: str\n"
            "    def days_until_expiry(self) -> int: ...\n"
        )
        result = pre_gate_interface_spec(artifact)
        assert result.passed
        assert result.ruff_passed
        assert result.diagnostics == []

    def test_auto_fixes_ruff_errors(self, tmp_path):
        artifact = tmp_path / "artifact.pyi"
        artifact.write_text("def hello() ->str:\n    return 'hello'\n")
        result = pre_gate_interface_spec(artifact)
        assert result.ruff_passed

    def test_fails_on_import_error(self, tmp_path):
        artifact = tmp_path / "artifact.pyi"
        artifact.write_text("from nonexistent_module import Foo\nclass Bar:\n    foo: Foo\n")
        result = pre_gate_interface_spec(artifact)
        assert not result.passed
        assert any("import" in d.lower() or "ModuleNotFoundError" in d for d in result.diagnostics)

    def test_passes_with_valid_dependency(self, tmp_path):
        artifact = tmp_path / "artifact.pyi"
        artifact.write_text(
            "from certificate_model import Certificate\nclass Scanner:\n    cert: Certificate\n"
        )
        dep_pyi = tmp_path / "dep.pyi"
        dep_pyi.write_text("class Certificate:\n    subject: str\n")
        result = pre_gate_interface_spec(
            artifact,
            dependency_pyi_paths=[("certificate_model", dep_pyi)],
        )
        assert result.passed

    def test_missing_artifact_fails(self, tmp_path):
        artifact = tmp_path / "nonexistent.pyi"
        result = pre_gate_interface_spec(artifact)
        assert not result.passed
        assert any("not found" in d.lower() for d in result.diagnostics)

    def test_import_check_catches_syntax_error(self, tmp_path):
        artifact = tmp_path / "artifact.pyi"
        artifact.write_text("class Foo(:\n    bar: str\n")
        result = pre_gate_interface_spec(artifact)
        assert not result.passed

    def test_ruff_auto_fix_copies_back(self, tmp_path):
        original_content = "def hello() ->str:\n    return 'hello'\n"
        artifact = tmp_path / "artifact.pyi"
        artifact.write_text(original_content)
        result = pre_gate_interface_spec(artifact)
        assert result.ruff_passed
        fixed = artifact.read_text()
        assert fixed != original_content


class TestPreGateTestSuite:
    def test_passes_on_collectible_tests(self, tmp_path):
        artifact = tmp_path / "test_hello.py"
        artifact.write_text("def test_hello():\n    assert True\n")
        result = pre_gate_test_suite(artifact)
        assert result.passed
        assert result.diagnostics == []

    def test_auto_fixes_ruff_errors(self, tmp_path):
        artifact = tmp_path / "test_hello.py"
        artifact.write_text("def hello() -> str:\n    x=1+2\n    return 'hello'\n")
        result = pre_gate_test_suite(artifact)
        assert result.ruff_passed

    def test_fails_on_collection_error(self, tmp_path):
        artifact = tmp_path / "test_bad.py"
        artifact.write_text(
            "from nonexistent_module import foo\ndef test_foo():\n    assert foo() == 1\n"
        )
        result = pre_gate_test_suite(artifact)
        assert not result.passed
        assert not result.pytest_passed

    def test_passes_with_interface_import(self, tmp_path):
        artifact = tmp_path / "test_iface.py"
        artifact.write_text(
            "from interface import add\ndef test_add():\n    assert add(1, 2) == 3\n"
        )
        interface_pyi = tmp_path / "interface.pyi"
        interface_pyi.write_text("def add(a: int, b: int) -> int: ...\n")
        result = pre_gate_test_suite(
            artifact,
            interface_pyi_path=interface_pyi,
        )
        assert result.passed

    def test_passes_with_dependency(self, tmp_path):
        artifact = tmp_path / "test_cert.py"
        artifact.write_text(
            "from certificate_model import Certificate\n"
            "def test_cert():\n"
            "    c = Certificate(subject='test')\n"
            "    assert c.subject == 'test'\n"
        )
        dep_pyi = tmp_path / "dep.pyi"
        dep_pyi.write_text("class Certificate:\n    subject: str\n")
        result = pre_gate_test_suite(
            artifact,
            dependency_pyi_paths=[("certificate_model", dep_pyi)],
        )
        assert result.passed

    def test_missing_artifact_fails(self, tmp_path):
        artifact = tmp_path / "nonexistent.py"
        result = pre_gate_test_suite(artifact)
        assert not result.passed
        assert any("not found" in d.lower() for d in result.diagnostics)

    def test_collect_only_does_not_run_tests(self, tmp_path):
        artifact = tmp_path / "test_fail.py"
        artifact.write_text("def test_always_fails():\n    assert False\n")
        result = pre_gate_test_suite(artifact)
        assert result.passed


class TestPreGateDispatch:
    def test_interface_architect_uses_import_check(self, tmp_path):
        from factory.runner import _run_pre_gate

        artifact = tmp_path / "artifact.pyi"
        artifact.write_text("class Foo:\n    bar: str\n")
        deps = PreGateDeps(
            interface_pyi_path=None,
            dep_paths=None,
            python_executable=None,
            test_suite_path=None,
        )
        result = _run_pre_gate("interface_architect", artifact, deps)
        assert result.passed

    def test_test_author_uses_collect_only(self, tmp_path):
        from factory.runner import _run_pre_gate

        artifact = tmp_path / "test_hello.py"
        artifact.write_text("def test_hello():\n    assert True\n")
        deps = PreGateDeps(
            interface_pyi_path=None,
            dep_paths=None,
            python_executable=None,
            test_suite_path=None,
        )
        result = _run_pre_gate("test_author", artifact, deps)
        assert result.passed

    def test_implementer_uses_full_gate(self, tmp_path):
        from factory.runner import _run_pre_gate

        artifact = tmp_path / "interface.py"
        artifact.write_text("def hello() -> str:\n    return 'hello'\n")
        interface_pyi = tmp_path / "interface.pyi"
        interface_pyi.write_text("def hello() -> str: ...\n")
        deps = PreGateDeps(
            interface_pyi_path=interface_pyi,
            dep_paths=None,
            python_executable=None,
            test_suite_path=None,
        )
        result = _run_pre_gate("implementer", artifact, deps)
        assert result.passed


class TestRunRuffFastAutoFix:
    def test_auto_fix_returns_fixed_content(self, tmp_path):
        from factory.pre_gate import _run_ruff_fast

        artifact = tmp_path / "impl.py"
        original = "x=1\n"
        artifact.write_text(original)
        result = _run_ruff_fast(artifact)
        assert result["passed"]
        assert artifact.read_text() == original
        assert result.get("ruff_fixed_content") is not None
        assert "x = 1" in result["ruff_fixed_content"]

    def test_apply_ruff_fix_writes_back(self, tmp_path):
        from factory.pre_gate import _apply_ruff_fix, _run_ruff_fast

        artifact = tmp_path / "impl.py"
        original = "x=1\n"
        artifact.write_text(original)
        result = _run_ruff_fast(artifact)
        assert result["passed"]
        assert result.get("ruff_fixed_content") is not None
        _apply_ruff_fix(artifact, result["ruff_fixed_content"])
        fixed = artifact.read_text()
        assert fixed != original
        assert "x = 1" in fixed

    def test_apply_ruff_fix_saves_orig_backup(self, tmp_path):
        from factory.pre_gate import _apply_ruff_fix, _run_ruff_fast

        artifact = tmp_path / "impl.py"
        original = "x=1\n"
        artifact.write_text(original)
        result = _run_ruff_fast(artifact)
        _apply_ruff_fix(artifact, result["ruff_fixed_content"])
        orig = tmp_path / ".impl.py.orig"
        assert orig.exists()
        assert orig.read_text() == original

    def test_no_fixed_content_when_unchanged(self, tmp_path):
        from factory.pre_gate import _run_ruff_fast

        artifact = tmp_path / "impl.py"
        artifact.write_text("x = 1\n")
        result = _run_ruff_fast(artifact)
        assert result["passed"]
        assert result.get("ruff_fixed_content") is None

    def test_unfixable_error_fails(self, tmp_path):
        from factory.pre_gate import _run_ruff_fast

        artifact = tmp_path / "impl.py"
        artifact.write_text("print(undefined_name)\n")
        result = _run_ruff_fast(artifact)
        assert not result["passed"]

    def test_e501_long_line_passes(self, tmp_path):
        from factory.pre_gate import _run_ruff_fast

        artifact = tmp_path / "impl.py"
        long_line = "x = " + '"a"' * 50 + "\n"
        artifact.write_text(long_line)
        result = _run_ruff_fast(artifact)
        assert result["passed"]


class TestPreGateIntegrator:
    def _valid_artifact(self) -> dict:
        return {
            "assembled_tree": {
                "__init__.py": "",
                "module.py": "def func() -> int:\n    return 1\n",
            },
            "entry_point": "module.func",
            "integration_tests": "def test_func():\n    assert True\n",
        }

    def test_passes_on_valid_artifact(self, tmp_path):
        import json

        artifact = tmp_path / "artifact.json"
        artifact.write_text(json.dumps(self._valid_artifact()))
        result = pre_gate_integrator(artifact)
        assert result.passed
        assert result.diagnostics == []
        assert result.mypy_passed
        assert result.ruff_passed
        assert result.pytest_passed

    def test_missing_artifact_fails(self, tmp_path):
        artifact = tmp_path / "nonexistent.json"
        result = pre_gate_integrator(artifact)
        assert not result.passed
        assert any("not found" in d.lower() for d in result.diagnostics)

    def test_invalid_json_fails(self, tmp_path):
        artifact = tmp_path / "artifact.json"
        artifact.write_text("{'single': 'quotes'}")
        result = pre_gate_integrator(artifact)
        assert not result.passed
        assert any("not valid JSON" in d for d in result.diagnostics)

    def test_non_dict_json_fails(self, tmp_path):
        import json

        artifact = tmp_path / "artifact.json"
        artifact.write_text(json.dumps([1, 2, 3]))
        result = pre_gate_integrator(artifact)
        assert not result.passed
        assert any("must be an object" in d for d in result.diagnostics)

    def test_cannot_proceed_passes(self, tmp_path):
        import json

        artifact = tmp_path / "artifact.json"
        artifact.write_text(json.dumps({"status": "cannot_proceed", "reason": "stuck"}))
        result = pre_gate_integrator(artifact)
        assert result.passed

    def test_cannot_proceed_without_reason_fails(self, tmp_path):
        import json

        artifact = tmp_path / "artifact.json"
        artifact.write_text(json.dumps({"status": "cannot_proceed"}))
        result = pre_gate_integrator(artifact)
        assert not result.passed
        assert any("reason" in d for d in result.diagnostics)

    def test_cannot_proceed_empty_reason_fails(self, tmp_path):
        import json

        artifact = tmp_path / "artifact.json"
        artifact.write_text(json.dumps({"status": "cannot_proceed", "reason": "  "}))
        result = pre_gate_integrator(artifact)
        assert not result.passed

    def test_missing_required_keys_fails(self, tmp_path):
        import json

        artifact = tmp_path / "artifact.json"
        artifact.write_text(json.dumps({"assembled_tree": {}}))
        result = pre_gate_integrator(artifact)
        assert not result.passed
        assert any("Missing required keys" in d for d in result.diagnostics)

    def test_empty_assembled_tree_fails(self, tmp_path):
        import json

        data = self._valid_artifact()
        data["assembled_tree"] = {}
        artifact = tmp_path / "artifact.json"
        artifact.write_text(json.dumps(data))
        result = pre_gate_integrator(artifact)
        assert not result.passed
        assert any("assembled_tree" in d for d in result.diagnostics)

    def test_non_string_tree_values_fails(self, tmp_path):
        import json

        data = self._valid_artifact()
        data["assembled_tree"]["bad.py"] = 42
        artifact = tmp_path / "artifact.json"
        artifact.write_text(json.dumps(data))
        result = pre_gate_integrator(artifact)
        assert not result.passed
        assert any("non-string" in d.lower() for d in result.diagnostics)

    def test_entry_point_without_dot_fails(self, tmp_path):
        import json

        data = self._valid_artifact()
        data["entry_point"] = "nodulefunc"
        artifact = tmp_path / "artifact.json"
        artifact.write_text(json.dumps(data))
        result = pre_gate_integrator(artifact)
        assert not result.passed
        assert any("dotted reference" in d for d in result.diagnostics)

    def test_entry_point_module_not_in_tree_fails(self, tmp_path):
        import json

        data = self._valid_artifact()
        data["entry_point"] = "nonexistent.func"
        del data["assembled_tree"]["__init__.py"]
        artifact = tmp_path / "artifact.json"
        artifact.write_text(json.dumps(data))
        result = pre_gate_integrator(artifact)
        assert not result.passed
        assert any("not present" in d for d in result.diagnostics)

    def test_entry_point_module_in_tree_passes_without_init(self, tmp_path):
        import json

        data = {
            "assembled_tree": {"module.py": "def func(): pass\n"},
            "entry_point": "module.func",
            "integration_tests": "def test_func(): pass\n",
        }
        artifact = tmp_path / "artifact.json"
        artifact.write_text(json.dumps(data))
        result = pre_gate_integrator(artifact)
        assert result.passed

    def test_empty_integration_tests_fails(self, tmp_path):
        import json

        data = self._valid_artifact()
        data["integration_tests"] = "   "
        artifact = tmp_path / "artifact.json"
        artifact.write_text(json.dumps(data))
        result = pre_gate_integrator(artifact)
        assert not result.passed
        assert any("integration_tests" in d for d in result.diagnostics)


class TestPreGateOutcomeVerifier:
    def _valid_pass_artifact(self) -> dict:
        return {
            "verdict": "pass",
            "rationale": "All integration tests pass.",
            "routing_hint": None,
        }

    def _valid_fail_artifact(self) -> dict:
        return {
            "verdict": "fail",
            "rationale": "Integration tests failed.",
            "routing_hint": {"target_role": "implementer", "work_item_id": "abc-123"},
        }

    def test_passes_on_pass_verdict(self, tmp_path):
        import json

        artifact = tmp_path / "artifact.json"
        artifact.write_text(json.dumps(self._valid_pass_artifact()))
        result = pre_gate_outcome_verifier(artifact)
        assert result.passed
        assert result.diagnostics == []
        assert result.mypy_passed
        assert result.ruff_passed
        assert result.pytest_passed

    def test_passes_on_fail_verdict_with_routing_hint(self, tmp_path):
        import json

        artifact = tmp_path / "artifact.json"
        artifact.write_text(json.dumps(self._valid_fail_artifact()))
        result = pre_gate_outcome_verifier(artifact)
        assert result.passed

    def test_passes_on_cannot_proceed_verdict(self, tmp_path):
        import json

        data = {
            "verdict": "cannot_proceed",
            "rationale": "Cannot verify.",
            "routing_hint": None,
        }
        artifact = tmp_path / "artifact.json"
        artifact.write_text(json.dumps(data))
        result = pre_gate_outcome_verifier(artifact)
        assert result.passed

    def test_missing_artifact_fails(self, tmp_path):
        artifact = tmp_path / "nonexistent.json"
        result = pre_gate_outcome_verifier(artifact)
        assert not result.passed
        assert any("not found" in d.lower() for d in result.diagnostics)

    def test_invalid_json_fails(self, tmp_path):
        artifact = tmp_path / "artifact.json"
        artifact.write_text("not json at all")
        result = pre_gate_outcome_verifier(artifact)
        assert not result.passed
        assert any("not valid JSON" in d for d in result.diagnostics)

    def test_missing_required_keys_fails(self, tmp_path):
        import json

        artifact = tmp_path / "artifact.json"
        artifact.write_text(json.dumps({"verdict": "pass"}))
        result = pre_gate_outcome_verifier(artifact)
        assert not result.passed
        assert any("Missing required keys" in d for d in result.diagnostics)

    def test_invalid_verdict_fails(self, tmp_path):
        import json

        data = {
            "verdict": "maybe",
            "rationale": "Unclear.",
            "routing_hint": None,
        }
        artifact = tmp_path / "artifact.json"
        artifact.write_text(json.dumps(data))
        result = pre_gate_outcome_verifier(artifact)
        assert not result.passed
        assert any("verdict" in d.lower() for d in result.diagnostics)

    def test_empty_rationale_fails(self, tmp_path):
        import json

        data = {
            "verdict": "pass",
            "rationale": "  ",
            "routing_hint": None,
        }
        artifact = tmp_path / "artifact.json"
        artifact.write_text(json.dumps(data))
        result = pre_gate_outcome_verifier(artifact)
        assert not result.passed
        assert any("rationale" in d for d in result.diagnostics)

    def test_pass_with_non_null_routing_hint_fails(self, tmp_path):
        import json

        data = {
            "verdict": "pass",
            "rationale": "OK.",
            "routing_hint": {"target": "implementer"},
        }
        artifact = tmp_path / "artifact.json"
        artifact.write_text(json.dumps(data))
        result = pre_gate_outcome_verifier(artifact)
        assert not result.passed
        assert any("routing_hint" in d and "null" in d for d in result.diagnostics)

    def test_fail_with_non_dict_routing_hint_fails(self, tmp_path):
        import json

        data = {
            "verdict": "fail",
            "rationale": "Broken.",
            "routing_hint": "fix it",
        }
        artifact = tmp_path / "artifact.json"
        artifact.write_text(json.dumps(data))
        result = pre_gate_outcome_verifier(artifact)
        assert not result.passed
        assert any("routing_hint" in d and "object" in d for d in result.diagnostics)


class TestPreGateDispatchJson:
    def test_integrator_uses_json_pre_gate(self, tmp_path):
        import json

        from factory.runner import _run_pre_gate

        data = {
            "assembled_tree": {"mod.py": "def f(): pass\n"},
            "entry_point": "mod.f",
            "integration_tests": "def test_f(): pass\n",
        }
        artifact = tmp_path / "artifact.json"
        artifact.write_text(json.dumps(data))
        deps = PreGateDeps(
            interface_pyi_path=None,
            dep_paths=None,
            python_executable=None,
            test_suite_path=None,
        )
        result = _run_pre_gate("integrator", artifact, deps)
        assert result.passed

    def test_integrator_invalid_json_fails(self, tmp_path):
        from factory.runner import _run_pre_gate

        artifact = tmp_path / "artifact.json"
        artifact.write_text("not json")
        deps = PreGateDeps(
            interface_pyi_path=None,
            dep_paths=None,
            python_executable=None,
            test_suite_path=None,
        )
        result = _run_pre_gate("integrator", artifact, deps)
        assert not result.passed

    def test_outcome_verifier_uses_json_pre_gate(self, tmp_path):
        import json

        from factory.runner import _run_pre_gate

        data = {
            "verdict": "pass",
            "rationale": "OK.",
            "routing_hint": None,
        }
        artifact = tmp_path / "artifact.json"
        artifact.write_text(json.dumps(data))
        deps = PreGateDeps(
            interface_pyi_path=None,
            dep_paths=None,
            python_executable=None,
            test_suite_path=None,
        )
        result = _run_pre_gate("outcome_verifier", artifact, deps)
        assert result.passed

    def test_integrator_does_not_run_ruff(self, tmp_path):
        import json

        from factory.runner import _run_pre_gate

        artifact = tmp_path / "artifact.json"
        artifact.write_text(json.dumps({"status": "cannot_proceed", "reason": "stuck"}))
        deps = PreGateDeps(
            interface_pyi_path=None,
            dep_paths=None,
            python_executable=None,
            test_suite_path=None,
        )
        result = _run_pre_gate("integrator", artifact, deps)
        assert result.passed
        assert result.ruff_passed
        assert result.mypy_passed
        assert result.pytest_passed
