from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from factory.constants import (
    GATE_NAME_IMPLEMENTATION_FILE_EXISTS,
    GATE_NAME_IMPLEMENTATION_NOT_EMPTY,
    GATE_NAME_IMPLEMENTATION_SYNTAX,
    GATE_NAME_MUTATION_SPOT_CHECK,
)
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
        assert result.gate_name == GATE_NAME_IMPLEMENTATION_FILE_EXISTS
        assert result.diagnostic_kind == "file_exists"

    def test_empty_file(self, artifact_dir):
        path = _write(artifact_dir, "empty.py", "")
        result = evaluate_implementation(path)
        assert not result.passed
        assert result.gate_name == GATE_NAME_IMPLEMENTATION_NOT_EMPTY
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
        assert result.gate_name == GATE_NAME_IMPLEMENTATION_SYNTAX
        assert result.diagnostic_kind == "syntax"

    def test_passes_with_refs_provided(self, artifact_dir):
        impl_path = _write(
            artifact_dir,
            "compute.py",
            """
def compute(x: int) -> str:
    return str(x)
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
            interface_pyi_path=iface_path,
        )
        assert result.passed


class TestMutationGatePath:
    """Tests for optional mutation gate integration in evaluate_implementation."""

    IMPL_STRICT = """
def max_of(a: int, b: int) -> int:
    if a > b:
        return a
    return b
"""

    SUITE_STRICT = """
import pytest

def test_max_of_basic():
    from max_of import max_of
    assert max_of(3, 1) == 3
    assert max_of(1, 3) == 3
    assert max_of(2, 2) == 2
"""

    IMPL_LAX = """
def classify(x: int) -> str:
    if x > 10:
        return "big"
    return "small"
"""

    SUITE_LAX = """
def test_classify_small():
    from classify import classify
    assert classify(5) == "small"
"""

    def test_mutation_disabled_skips_gate(self, artifact_dir):
        impl_path = _write(artifact_dir, "max_of.py", self.IMPL_STRICT)
        suite_path = _write(artifact_dir, "test_max_of.py", self.SUITE_STRICT)
        result = evaluate_implementation(
            impl_path,
            test_suite_path=suite_path,
            mutation_enabled=False,
        )
        assert result.passed
        assert result.gate_name != GATE_NAME_MUTATION_SPOT_CHECK

    def test_mutation_enabled_passes_strict_tests(self, artifact_dir):
        impl_path = _write(artifact_dir, "max_of.py", self.IMPL_STRICT)
        suite_path = _write(artifact_dir, "test_max_of.py", self.SUITE_STRICT)
        result = evaluate_implementation(
            impl_path,
            test_suite_path=suite_path,
            mutation_enabled=True,
            mutation_sample_size=3,
            mutation_fail_threshold=0.5,
            mutation_seed=42,
        )
        assert result.passed
        assert result.gate_name != GATE_NAME_MUTATION_SPOT_CHECK

    def test_mutation_enabled_fails_lax_tests(self, artifact_dir):
        impl_path = _write(artifact_dir, "classify.py", self.IMPL_LAX)
        suite_path = _write(artifact_dir, "test_classify.py", self.SUITE_LAX)
        result = evaluate_implementation(
            impl_path,
            test_suite_path=suite_path,
            mutation_enabled=True,
            mutation_sample_size=3,
            mutation_fail_threshold=0.0,
            mutation_seed=42,
        )
        assert not result.passed
        assert result.gate_name == GATE_NAME_MUTATION_SPOT_CHECK
        assert result.diagnostic_kind == "mutation_uncaught"
        assert "LIVE (missed)" in " ".join(result.diagnostics)

    def test_mutation_runs_after_pytest(self, artifact_dir):
        impl_path = _write(artifact_dir, "max_of.py", self.IMPL_STRICT)
        suite_path = _write(artifact_dir, "test_max_of.py", self.SUITE_STRICT)
        # mutation_enabled=True but missing interface_pyi_path — mypy will skip
        result = evaluate_implementation(
            impl_path,
            test_suite_path=suite_path,
            mutation_enabled=True,
            mutation_sample_size=1,
            mutation_fail_threshold=0.0,
            mutation_seed=42,
        )
        # Should still pass because strict tests catch the mutant
        assert result.passed
