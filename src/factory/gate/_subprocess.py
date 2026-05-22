from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

from factory.constants import (
    ARTIFACT_FILENAME_INTERFACE,
    GATE_NAME_IMPLEMENTATION_LINT,
    GATE_NAME_IMPLEMENTATION_MYPY,
    GATE_NAME_IMPLEMENTATION_PYTEST,
    GATE_NAME_TEST_SUITE_COLLECT,
    TEMPFILE_PREFIX_COLLECT,
    TEMPFILE_PREFIX_MYPY,
    TEMPFILE_PREFIX_PYTEST,
)
from factory.gate._base import GateResult
from factory.pre_gate import copy_dependency_pyis
from factory.sandbox import gate_subprocess_env
from factory.subprocess import run as run_subprocess


# tier: enforce
# precondition: shared by implementation, test_suite gates; wraps mypy/pytest/ruff subprocesses
# audit trigger: re-evaluate if subprocess isolation model changes
def _run_pytest_collect(
    artifact_path: Path,
    interface_ref_pyi_path: Path | None = None,
    dependency_pyi_paths: list[tuple[str, Path]] | None = None,
    dependency_spec_paths: list[tuple[str, Path]] | None = None,
    python_executable: str | None = None,
    timeout: int = 30,
) -> GateResult:
    exe = python_executable or sys.executable
    try:
        with tempfile.TemporaryDirectory(prefix=TEMPFILE_PREFIX_COLLECT) as tmpdir:
            test_copy = Path(tmpdir) / artifact_path.name
            test_copy.write_text(artifact_path.read_text())
            if interface_ref_pyi_path is not None and interface_ref_pyi_path.exists():
                iface_copy = Path(tmpdir) / "interface.py"
                iface_copy.write_text(interface_ref_pyi_path.read_text())
            copy_dependency_pyis(tmpdir, dependency_pyi_paths, dependency_spec_paths)
            result = run_subprocess(
                cmd=[exe, "-m", "pytest", "--collect-only", "-q", str(test_copy)],
                cwd=Path(tmpdir),
                env=gate_subprocess_env(PYTHONPATH=tmpdir),
                timeout_s=timeout,
            )
            if result.timed_out:
                return GateResult(
                    passed=False,
                    gate_name=GATE_NAME_TEST_SUITE_COLLECT,
                    diagnostics=[f"pytest --collect-only timed out after {timeout}s"],
                    diagnostic_kind="test_collect",
                )
            if result.returncode != 0:
                if "No module named pytest" in result.stderr:
                    return GateResult(
                        passed=False,
                        gate_name=GATE_NAME_TEST_SUITE_COLLECT,
                        diagnostics=["pytest not installed"],
                        diagnostic_kind="tool_not_found",
                    )
                lines = result.stdout.strip().splitlines() + result.stderr.strip().splitlines()
                diagnostics = lines[:10] or ["pytest --collect-only failed"]
                return GateResult(
                    passed=False,
                    gate_name=GATE_NAME_TEST_SUITE_COLLECT,
                    diagnostics=diagnostics,
                    diagnostic_kind="test_collect",
                )
            no_tests = (
                "no tests collected" in result.stdout.lower()
                or "no tests ran" in result.stdout.lower()
            )
            if no_tests:
                return GateResult(
                    passed=False,
                    gate_name=GATE_NAME_TEST_SUITE_COLLECT,
                    diagnostics=["pytest --collect-only reported 0 tests"],
                    diagnostic_kind="test_collect",
                )
    except Exception as e:
        return GateResult(
            passed=False,
            gate_name=GATE_NAME_TEST_SUITE_COLLECT,
            diagnostics=[f"pytest --collect-only failed: {e}"],
            diagnostic_kind="test_collect",
        )
    return GateResult(passed=True, gate_name=GATE_NAME_TEST_SUITE_COLLECT)


def _run_mypy(
    artifact_path: Path,
    interface_pyi_path: Path,
    dependency_pyi_paths: list[tuple[str, Path]] | None = None,
    dependency_spec_paths: list[tuple[str, Path]] | None = None,
    python_executable: str | None = None,
    timeout: int = 120,
) -> GateResult:
    exe = python_executable or sys.executable
    if interface_pyi_path is None or not interface_pyi_path.exists():
        return GateResult(
            passed=False,
            gate_name=GATE_NAME_IMPLEMENTATION_MYPY,
            diagnostics=["missing interface .pyi, cannot type-check"],
            diagnostic_kind="missing_artifact",
        )
    try:
        with tempfile.TemporaryDirectory(prefix=TEMPFILE_PREFIX_MYPY) as tmpdir:
            impl_copy = Path(tmpdir) / "interface.py"
            impl_copy.write_text(artifact_path.read_text())
            stub_copy = Path(tmpdir) / "interface.pyi"
            stub_copy.write_text(interface_pyi_path.read_text())
            copy_dependency_pyis(tmpdir, dependency_pyi_paths, dependency_spec_paths)
            result = run_subprocess(
                cmd=[
                    exe,
                    "-m",
                    "mypy",
                    "--strict",
                    "--no-error-summary",
                    # BC-176/184: suppress [empty-body] on .pyi stubs so that
                    # interface ellipsis-body stubs don't fail implementation mypy.
                    "--allow-empty-bodies",
                    str(impl_copy),
                ],
                cwd=Path(tmpdir),
                env=gate_subprocess_env(MYPYPATH=tmpdir),
                timeout_s=timeout,
            )
            if result.timed_out:
                return GateResult(
                    passed=False,
                    gate_name=GATE_NAME_IMPLEMENTATION_MYPY,
                    diagnostics=[f"mypy timed out after {timeout}s", "timed_out: True"],
                    diagnostic_kind="impl_mypy",
                )
            if result.returncode != 0:
                if "No module named mypy" in result.stderr:
                    return GateResult(
                        passed=False,
                        gate_name=GATE_NAME_IMPLEMENTATION_MYPY,
                        diagnostics=["mypy not installed"],
                        diagnostic_kind="tool_not_found",
                    )
                lines = result.stdout.strip().splitlines()
                diagnostics = lines[:10] if lines else ["mypy reported errors"]
                return GateResult(
                    passed=False,
                    gate_name=GATE_NAME_IMPLEMENTATION_MYPY,
                    diagnostics=diagnostics,
                    diagnostic_kind="impl_mypy",
                )
    except Exception as e:
        return GateResult(
            passed=False,
            gate_name=GATE_NAME_IMPLEMENTATION_MYPY,
            diagnostics=[f"mypy invocation failed: {e}"],
            diagnostic_kind="impl_mypy",
        )
    return GateResult(passed=True, gate_name=GATE_NAME_IMPLEMENTATION_MYPY)


def _run_pytest(
    artifact_path: Path,
    test_suite_path: Path,
    dependency_pyi_paths: list[tuple[str, Path]] | None = None,
    dependency_spec_paths: list[tuple[str, Path]] | None = None,
    python_executable: str | None = None,
    timeout: int = 300,
) -> GateResult:
    exe = python_executable or sys.executable
    try:
        with tempfile.TemporaryDirectory(prefix=TEMPFILE_PREFIX_PYTEST) as tmpdir:
            impl_content = artifact_path.read_text()
            impl_copy = Path(tmpdir) / artifact_path.name
            impl_copy.write_text(impl_content)
            if artifact_path.stem != ARTIFACT_FILENAME_INTERFACE:
                iface_copy = Path(tmpdir) / f"interface{artifact_path.suffix}"
                iface_copy.write_text(impl_content)
            test_copy = Path(tmpdir) / test_suite_path.name
            test_copy.write_text(test_suite_path.read_text())
            copy_dependency_pyis(tmpdir, dependency_pyi_paths, dependency_spec_paths)
            result = run_subprocess(
                cmd=[
                    exe,
                    "-m",
                    "pytest",
                    str(test_copy),
                    "-x",
                    "--tb=short",
                    "-q",
                ],
                cwd=Path(tmpdir),
                env=gate_subprocess_env(PYTHONPATH=tmpdir),
                timeout_s=timeout,
            )
            if result.timed_out:
                return GateResult(
                    passed=False,
                    gate_name=GATE_NAME_IMPLEMENTATION_PYTEST,
                    diagnostics=[f"pytest timed out after {timeout}s", "timed_out: True"],
                    diagnostic_kind="impl_pytest",
                )
            if result.returncode != 0:
                if "No module named pytest" in result.stderr:
                    return GateResult(
                        passed=False,
                        gate_name=GATE_NAME_IMPLEMENTATION_PYTEST,
                        diagnostics=["pytest not installed"],
                        diagnostic_kind="tool_not_found",
                    )
                lines = result.stdout.strip().splitlines()
                err_lines = result.stderr.strip().splitlines()
                diagnostics = (lines + err_lines)[:10] or ["pytest reported failures"]
                return GateResult(
                    passed=False,
                    gate_name=GATE_NAME_IMPLEMENTATION_PYTEST,
                    diagnostics=diagnostics,
                    diagnostic_kind="impl_pytest",
                )
    except Exception as e:
        return GateResult(
            passed=False,
            gate_name=GATE_NAME_IMPLEMENTATION_PYTEST,
            diagnostics=[f"pytest invocation failed: {e}"],
            diagnostic_kind="impl_pytest",
        )
    return GateResult(passed=True, gate_name=GATE_NAME_IMPLEMENTATION_PYTEST)


def _run_ruff(
    artifact_path: Path,
    python_executable: str | None = None,
    timeout: int = 60,
) -> GateResult:
    ruff = shutil.which("ruff") or shutil.which("ruff", path=str(Path(sys.prefix) / "bin"))
    if ruff is None:
        return GateResult(
            passed=False,
            gate_name=GATE_NAME_IMPLEMENTATION_LINT,
            diagnostics=["ruff not installed"],
            diagnostic_kind="tool_not_found",
        )
    try:
        with tempfile.TemporaryDirectory(prefix="sf2_ruff_") as tmpdir:
            tmp_copy = Path(tmpdir) / artifact_path.name
            tmp_copy.write_text(artifact_path.read_text())
            ruff_env = gate_subprocess_env()
            run_subprocess(
                cmd=[ruff, "check", "--fix", str(tmp_copy)],
                cwd=Path(tmpdir),
                env=ruff_env,
                timeout_s=timeout,
            )
            run_subprocess(
                cmd=[ruff, "format", str(tmp_copy)],
                cwd=Path(tmpdir),
                env=ruff_env,
                timeout_s=timeout,
            )
            result = run_subprocess(
                cmd=[ruff, "check", str(tmp_copy)],
                cwd=Path(tmpdir),
                env=ruff_env,
                timeout_s=timeout,
            )
            if result.timed_out:
                return GateResult(
                    passed=False,
                    gate_name=GATE_NAME_IMPLEMENTATION_LINT,
                    diagnostics=[f"ruff timed out after {timeout}s", "timed_out: True"],
                    diagnostic_kind="impl_lint",
                )
            if result.returncode != 0:
                lines = result.stdout.strip().splitlines()
                diagnostics = lines[:10] if lines else ["ruff reported lint issues"]
                return GateResult(
                    passed=False,
                    gate_name=GATE_NAME_IMPLEMENTATION_LINT,
                    diagnostics=diagnostics,
                    diagnostic_kind="impl_lint",
                )
    except Exception as e:
        return GateResult(
            passed=False,
            gate_name=GATE_NAME_IMPLEMENTATION_LINT,
            diagnostics=[f"ruff invocation failed: {e}"],
            diagnostic_kind="impl_lint",
        )
    return GateResult(passed=True, gate_name=GATE_NAME_IMPLEMENTATION_LINT)
