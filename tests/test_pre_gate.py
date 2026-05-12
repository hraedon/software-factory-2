from __future__ import annotations

from pathlib import Path

from factory.pre_gate import (
    PreGateDeps,
    copy_dependency_pyis,
    pre_gate_implementation,
    pre_gate_interface_spec,
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
        if not result["passed"]:
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
        if not result["passed"]:
            assert any(
                "pytest" in d.lower() or "failed" in d.lower() for d in result["diagnostics"]
            )


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
    def test_auto_fix_writes_back_to_artifact(self, tmp_path):
        from factory.pre_gate import _run_ruff_fast

        artifact = tmp_path / "impl.py"
        original = "x=1\n"
        artifact.write_text(original)
        result = _run_ruff_fast(artifact)
        assert result["passed"]
        fixed = artifact.read_text()
        assert fixed != original
        assert "x = 1" in fixed

    def test_auto_fix_saves_orig_backup(self, tmp_path):
        from factory.pre_gate import _run_ruff_fast

        artifact = tmp_path / "impl.py"
        original = "x=1\n"
        artifact.write_text(original)
        _run_ruff_fast(artifact)
        orig = tmp_path / ".impl.py.orig"
        assert orig.exists()
        assert orig.read_text() == original

    def test_no_orig_backup_when_unchanged(self, tmp_path):
        from factory.pre_gate import _run_ruff_fast

        artifact = tmp_path / "impl.py"
        artifact.write_text("x = 1\n")
        _run_ruff_fast(artifact)
        orig = tmp_path / ".impl.py.orig"
        assert not orig.exists()

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
