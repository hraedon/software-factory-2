from __future__ import annotations

from pathlib import Path

from factory.pre_gate import PreGateDeps, copy_dependency_pyis, pre_gate_implementation


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

    def test_fails_on_ruff_error(self, tmp_path):
        artifact = tmp_path / "interface.py"
        artifact.write_text("def hello() -> str:\n    x=1+2\n    return 'hello'\n")
        interface_pyi = tmp_path / "interface.pyi"
        interface_pyi.write_text("def hello() -> str: ...\n")
        result = pre_gate_implementation(artifact, interface_pyi_path=interface_pyi)
        assert not result.passed
        assert not result.ruff_passed

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


class TestCopyDependencyPyis:
    def test_writes_module_name_files(self, tmp_path):
        import tempfile

        dep_pyi = tmp_path / "dep.pyi"
        dep_pyi.write_text("class Foo:\n    bar: str\n")
        with tempfile.TemporaryDirectory(prefix="sf2_test_") as tmpdir:
            copy_dependency_pyis(tmpdir, [("my_module", dep_pyi)])
            assert (Path(tmpdir) / "my_module.py").exists()
            assert (Path(tmpdir) / "my_module.pyi").exists()
