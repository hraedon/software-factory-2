from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from factory.gate import evaluate_interface_spec


@pytest.fixture()
def artifact_dir(tmp_path):
    return tmp_path


def _write_stub(artifact_dir: Path, name: str, content: str) -> Path:
    p = artifact_dir / name
    p.write_text(textwrap.dedent(content))
    return p


class TestInterfaceSpecHappyPath:
    def test_valid_pyi(self, artifact_dir):
        stub = _write_stub(
            artifact_dir,
            "test.pyi",
            '''
from typing import Union

def parse_range(input: str, today: date) -> Union[Range, Error]:
    """Satisfies AC-01, AC-02."""
    ...
''',
        )
        result = evaluate_interface_spec(stub, ac_ids=["AC-01", "AC-02"])
        assert result.passed
        assert result.artifact_valid

    def test_valid_pyi_no_ac_ids(self, artifact_dir):
        stub = _write_stub(
            artifact_dir,
            "test.pyi",
            """
def foo(x: int) -> str: ...
""",
        )
        result = evaluate_interface_spec(stub)
        assert result.passed


class TestInterfaceSpecSyntaxError:
    def test_syntax_error(self, artifact_dir):
        stub = _write_stub(
            artifact_dir,
            "bad.pyi",
            """
def foo( -> int: ...
""",
        )
        result = evaluate_interface_spec(stub)
        assert not result.passed
        assert result.gate_name == "interface_spec_syntax"
        assert "SyntaxError" in result.diagnostics[0]


class TestInterfaceSpecStubCheck:
    def test_implementation_body(self, artifact_dir):
        stub = _write_stub(
            artifact_dir,
            "impl.py",
            """
def foo(x: int) -> str:
    return str(x)
""",
        )
        result = evaluate_interface_spec(stub)
        assert not result.passed
        assert "implementation body" in result.diagnostics[0]


class TestInterfaceSpecACReference:
    def test_missing_ac_reference(self, artifact_dir):
        stub = _write_stub(
            artifact_dir,
            "test.pyi",
            '''
def foo(x: int) -> str:
    """Satisfies AC-01."""
    ...
''',
        )
        result = evaluate_interface_spec(stub, ac_ids=["AC-01", "AC-02"])
        assert not result.passed
        assert result.gate_name == "interface_spec_ac_references"
        assert "AC-02" in result.diagnostics[0]

    def test_all_acs_present(self, artifact_dir):
        stub = _write_stub(
            artifact_dir,
            "test.pyi",
            '''
def foo(x: int) -> str:
    """Satisfies AC-01, AC-02."""
    ...
''',
        )
        result = evaluate_interface_spec(stub, ac_ids=["AC-01", "AC-02"])
        assert result.passed


class TestInterfaceSpecFileNotFound:
    def test_missing_file(self, artifact_dir):
        missing = artifact_dir / "nonexistent.pyi"
        result = evaluate_interface_spec(missing)
        assert not result.passed
        assert result.gate_name == "interface_spec_file_exists"

    def test_empty_file(self, artifact_dir):
        stub = _write_stub(artifact_dir, "empty.pyi", "")
        result = evaluate_interface_spec(stub)
        assert not result.passed
        assert result.gate_name == "interface_spec_not_empty"
