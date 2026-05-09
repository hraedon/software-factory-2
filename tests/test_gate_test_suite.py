from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from factory.constants import (
    GATE_NAME_TEST_SUITE_COLLECT,
    GATE_NAME_TEST_SUITE_FILE_EXISTS,
    GATE_NAME_TEST_SUITE_IMPORT_FORBIDDEN,
    GATE_NAME_TEST_SUITE_NOT_EMPTY,
    GATE_NAME_TEST_SUITE_SYNTAX,
)
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
        assert result.gate_name == GATE_NAME_TEST_SUITE_FILE_EXISTS
        assert result.diagnostic_kind == "file_exists"

    def test_empty_file(self, artifact_dir):
        path = _write(artifact_dir, "empty.py", "")
        result = evaluate_test_suite(path)
        assert not result.passed
        assert result.gate_name == GATE_NAME_TEST_SUITE_NOT_EMPTY
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
        assert result.gate_name == GATE_NAME_TEST_SUITE_SYNTAX
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
        assert result.gate_name == GATE_NAME_TEST_SUITE_IMPORT_FORBIDDEN
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


class TestTestSuiteCollectCheck:
    def test_file_with_no_test_functions_fails(self, artifact_dir):
        path = _write(
            artifact_dir,
            "helpers.py",
            """
def helper_a():
    return 1

def helper_b():
    return 2
""",
        )
        result = evaluate_test_suite(path)
        assert not result.passed
        assert result.gate_name == GATE_NAME_TEST_SUITE_COLLECT
        assert result.diagnostic_kind == "test_collect"

    def test_file_with_test_functions_passes(self, artifact_dir):
        path = _write(
            artifact_dir,
            "test_foo.py",
            """
def test_something():
    assert True
""",
        )
        result = evaluate_test_suite(path)
        assert result.passed

    def test_collect_failure_includes_diagnostic(self, artifact_dir):
        path = _write(
            artifact_dir,
            "empty_tests.py",
            """
x = 42
""",
        )
        result = evaluate_test_suite(path)
        assert not result.passed
        assert any("0 tests" in d or "collect" in d.lower() for d in result.diagnostics)
