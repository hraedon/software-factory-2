from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from factory.gate import evaluate_implementation


@pytest.fixture()
def artifact_dir(tmp_path):
    return tmp_path


def _write(artifact_dir: Path, name: str, content: str) -> Path:
    p = artifact_dir / name
    p.write_text(textwrap.dedent(content))
    return p


class TestImplementationHappyPath:
    def test_valid_python_file(self, artifact_dir):
        path = _write(
            artifact_dir,
            "impl.py",
            """
def compute(x: int) -> str:
    return str(x)
""",
        )
        result = evaluate_implementation(path)
        assert result.passed
        assert result.artifact_valid

    def test_accepts_no_refs(self, artifact_dir):
        path = _write(
            artifact_dir,
            "impl.py",
            """
def do_work(data: list[int]) -> int:
    return sum(data)
""",
        )
        result = evaluate_implementation(path)
        assert result.passed


class TestImplementationFailureModes:
    def test_file_not_found(self, artifact_dir):
        result = evaluate_implementation(artifact_dir / "nonexistent.py")
        assert not result.passed
        assert result.gate_name == "implementation_file_exists"
        assert result.diagnostic_kind == "file_exists"

    def test_empty_file(self, artifact_dir):
        path = _write(artifact_dir, "empty.py", "")
        result = evaluate_implementation(path)
        assert not result.passed
        assert result.gate_name == "implementation_not_empty"
        assert result.diagnostic_kind == "not_empty"

    def test_syntax_error(self, artifact_dir):
        path = _write(
            artifact_dir,
            "bad.py",
            """
def bad_code(
    return
""",
        )
        result = evaluate_implementation(path)
        assert not result.passed
        assert result.gate_name == "implementation_syntax"
        assert result.diagnostic_kind == "syntax"

    def test_passes_with_refs_provided(self, artifact_dir):
        impl_path = _write(
            artifact_dir,
            "impl.py",
            """
def compute(x: int) -> str:
    return str(x)
""",
        )
        ts_path = _write(
            artifact_dir,
            "test_compute.py",
            """
def test_compute():
    assert compute(1) == "1"
""",
        )
        iface_path = _write(
            artifact_dir,
            "iface.pyi",
            """
def compute(x: int) -> str: ...
""",
        )
        result = evaluate_implementation(
            impl_path,
            test_suite_path=ts_path,
            interface_pyi_path=iface_path,
        )
        assert result.passed
