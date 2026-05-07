from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from factory.gate import evaluate_test_suite


@pytest.fixture()
def artifact_dir(tmp_path):
    return tmp_path


def _write(artifact_dir: Path, name: str, content: str) -> Path:
    p = artifact_dir / name
    p.write_text(textwrap.dedent(content))
    return p


class TestTestSuiteHappyPath:
    def test_valid_python_file(self, artifact_dir):
        path = _write(
            artifact_dir,
            "test_foo.py",
            """
def test_foo(): ...
""",
        )
        result = evaluate_test_suite(path)
        assert result.passed
        assert result.artifact_valid

    def test_accepts_no_interface_ref(self, artifact_dir):
        path = _write(
            artifact_dir,
            "test_foo.py",
            """
def test_things() -> None:
    assert True
""",
        )
        result = evaluate_test_suite(path)
        assert result.passed


class TestTestSuiteFailureModes:
    def test_file_not_found(self, artifact_dir):
        result = evaluate_test_suite(artifact_dir / "nonexistent.py")
        assert not result.passed
        assert result.gate_name == "test_suite_file_exists"
        assert result.diagnostic_kind == "file_exists"

    def test_empty_file(self, artifact_dir):
        path = _write(artifact_dir, "empty.py", "")
        result = evaluate_test_suite(path)
        assert not result.passed
        assert result.gate_name == "test_suite_not_empty"
        assert result.diagnostic_kind == "not_empty"

    def test_syntax_error(self, artifact_dir):
        path = _write(
            artifact_dir,
            "bad.py",
            """
def test_foo(:
    pass
""",
        )
        result = evaluate_test_suite(path)
        assert not result.passed
        assert result.gate_name == "test_suite_syntax"
        assert result.diagnostic_kind == "syntax"

    def test_forbidden_import_when_interface_ref_provided(self, artifact_dir):
        path = _write(
            artifact_dir,
            "test_interface.py",
            """
from _impl import some_function

def test_foo():
    assert some_function() == 42
""",
        )
        interface_stub = _write(
            artifact_dir,
            "interface.pyi",
            "def some_function() -> int: ...\n",
        )
        result = evaluate_test_suite(path, interface_ref_pyi_path=interface_stub)
        assert not result.passed
        assert result.gate_name == "test_suite_import_forbidden"
        assert result.diagnostic_kind == "test_import_forbidden"
        assert "_impl" in result.diagnostics[0]

    def test_allowed_standard_library_import_passes(self, artifact_dir):
        path = _write(
            artifact_dir,
            "test_std.py",
            """
import os
import json

def test_foo():
    assert os.path.join("a", "b") == "a/b"
""",
        )
        interface_stub = _write(
            artifact_dir,
            "interface.pyi",
            "\n",
        )
        result = evaluate_test_suite(path, interface_ref_pyi_path=interface_stub)
        assert result.passed
