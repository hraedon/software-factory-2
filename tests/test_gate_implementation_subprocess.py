from __future__ import annotations

import shutil
import textwrap
from pathlib import Path

import pytest

from factory.constants import (
    GATE_NAME_IMPLEMENTATION_IMPORT_FORBIDDEN,
    GATE_NAME_IMPLEMENTATION_LINT,
    GATE_NAME_IMPLEMENTATION_PYTEST,
    GATE_NAME_IMPLEMENTATION_SYNTAX,
)
from factory.gate import evaluate_implementation


def _write(artifact_dir: Path, name: str, content: str) -> Path:
    p = artifact_dir / name
    p.write_text(textwrap.dedent(content))
    return p


class TestImplementationImportGate:
    def test_forbidden_pytest_import_when_interface_ref_provided(self, tmp_path):
        impl_path = _write(
            tmp_path,
            "impl.py",
            """
import pytest

def compute(x: int) -> str:
    return str(x)
""",
        )
        iface_path = _write(
            tmp_path,
            "iface.pyi",
            "def compute(x: int) -> str: ...\n",
        )
        result = evaluate_implementation(
            impl_path,
            interface_pyi_path=iface_path,
        )
        assert not result.passed
        assert result.gate_name == GATE_NAME_IMPLEMENTATION_IMPORT_FORBIDDEN
        assert result.diagnostic_kind == "impl_import"
        assert "pytest" in result.diagnostics[0]

    def test_forbidden_conftest_import(self, tmp_path):
        impl_path = _write(
            tmp_path,
            "impl.py",
            """
import conftest

def compute(x: int) -> str:
    return str(x)
""",
        )
        iface_path = _write(
            tmp_path,
            "iface.pyi",
            "def compute(x: int) -> str: ...\n",
        )
        result = evaluate_implementation(
            impl_path,
            interface_pyi_path=iface_path,
        )
        assert not result.passed
        assert result.diagnostic_kind == "impl_import"
        assert "conftest" in result.diagnostics[0]

    def test_normal_imports_pass(self, tmp_path):
        impl_path = tmp_path / "impl.py"
        impl_path.write_text("def compute(x: int) -> str:\n    return str(x)\n")
        iface_path = tmp_path / "iface.pyi"
        iface_path.write_text("def compute(x: int) -> str: ...\n")
        result = evaluate_implementation(
            impl_path,
            interface_pyi_path=iface_path,
        )
        assert result.passed


class TestImplementationRuffGate:
    @pytest.mark.skipif(not shutil.which("ruff"), reason="ruff not installed")
    def test_ruff_failure_returns_lint_diagnostic(self, tmp_path):
        impl_path = _write(
            tmp_path,
            "impl.py",
            "x = undefined_name\n",
        )
        result = evaluate_implementation(impl_path)
        assert not result.passed
        assert result.gate_name == GATE_NAME_IMPLEMENTATION_LINT
        assert result.diagnostic_kind == "impl_lint"
        assert len(result.diagnostics) > 0

    @pytest.mark.skipif(not shutil.which("ruff"), reason="ruff not installed")
    def test_clean_impl_passes_ruff(self, tmp_path):
        impl_path = _write(
            tmp_path,
            "impl.py",
            """
def compute(x: int) -> str:
    return str(x)
""",
        )
        result = evaluate_implementation(impl_path)
        assert result.passed


class TestImplementationPytestGate:
    @pytest.mark.skipif(not shutil.which("pytest"), reason="pytest not installed")
    def test_pytest_failure_returns_pytest_diagnostic(self, tmp_path):
        impl_path = _write(
            tmp_path,
            "compute.py",
            """
def compute(x: int) -> str:
    return "wrong"
""",
        )
        test_path = _write(
            tmp_path,
            "test_compute.py",
            """
from compute import compute

def test_compute():
    assert compute(1) == "1"
""",
        )
        result = evaluate_implementation(
            impl_path,
            test_suite_path=test_path,
        )
        assert not result.passed
        assert result.gate_name == GATE_NAME_IMPLEMENTATION_PYTEST
        assert result.diagnostic_kind == "impl_pytest"

    @pytest.mark.skipif(not shutil.which("pytest"), reason="pytest not installed")
    def test_pytest_pass_passes_gate(self, tmp_path):
        impl_path = _write(
            tmp_path,
            "compute.py",
            """
def compute(x: int) -> str:
    return str(x)
""",
        )
        test_path = _write(
            tmp_path,
            "test_compute.py",
            """
from compute import compute

def test_compute():
    assert compute(1) == "1"
""",
        )
        result = evaluate_implementation(
            impl_path,
            test_suite_path=test_path,
        )
        assert result.passed


class TestImplementationGateOrder:
    def test_syntax_checked_before_subprocess_gates(self, tmp_path):
        bad_path = _write(
            tmp_path,
            "bad.py",
            """
def bad(
    return
""",
        )
        iface_path = _write(tmp_path, "iface.pyi", "def bad() -> None: ...\n")
        result = evaluate_implementation(bad_path, interface_pyi_path=iface_path)
        assert not result.passed
        assert result.gate_name == GATE_NAME_IMPLEMENTATION_SYNTAX
        assert result.diagnostic_kind == "syntax"

    def test_import_checked_before_subprocess_gates(self, tmp_path):
        impl_path = _write(
            tmp_path,
            "impl.py",
            """
import pytest

def compute(x: int) -> str:
    return str(x)
""",
        )
        iface_path = _write(tmp_path, "iface.pyi", "def compute(x: int) -> str: ...\n")
        result = evaluate_implementation(impl_path, interface_pyi_path=iface_path)
        assert not result.passed
        assert result.diagnostic_kind == "impl_import"
