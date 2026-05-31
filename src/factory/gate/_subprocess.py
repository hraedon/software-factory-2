from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

from factory.config import GateTimeouts
from factory.constants import (
    ARTIFACT_FILENAME_INTERFACE,
    GATE_NAME_IMPLEMENTATION_LINT,
    GATE_NAME_IMPLEMENTATION_MYPY,
    GATE_NAME_IMPLEMENTATION_PYTEST,
    GATE_NAME_TEST_SUITE_COLLECT,
    GATE_NAME_VACUOUS_TEST,
    TEMPFILE_PREFIX_COLLECT,
    TEMPFILE_PREFIX_MYPY,
    TEMPFILE_PREFIX_PYTEST,
    DiagnosticKind,
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
                cmd=[
                    exe,
                    "-m",
                    "pytest",
                    "--collect-only",
                    "-q",
                    "-o",
                    "asyncio_mode=auto",
                    str(test_copy),
                ],
                cwd=Path(tmpdir),
                env=gate_subprocess_env(PYTHONPATH=tmpdir),
                timeout_s=timeout,
            )
            if result.timed_out:
                return GateResult(
                    passed=False,
                    gate_name=GATE_NAME_TEST_SUITE_COLLECT,
                    diagnostics=[f"pytest --collect-only timed out after {timeout}s"],
                    diagnostic_kind=DiagnosticKind.TEST_COLLECT,
                )
            if result.returncode != 0:
                if "No module named pytest" in result.stderr:
                    return GateResult(
                        passed=False,
                        gate_name=GATE_NAME_TEST_SUITE_COLLECT,
                        diagnostics=["pytest not installed"],
                        diagnostic_kind=DiagnosticKind.TOOL_NOT_FOUND,
                    )
                lines = result.stdout.strip().splitlines() + result.stderr.strip().splitlines()
                diagnostics = lines[:10] or ["pytest --collect-only failed"]
                return GateResult(
                    passed=False,
                    gate_name=GATE_NAME_TEST_SUITE_COLLECT,
                    diagnostics=diagnostics,
                    diagnostic_kind=DiagnosticKind.TEST_COLLECT,
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
                    diagnostic_kind=DiagnosticKind.TEST_COLLECT,
                )
    except Exception as e:
        return GateResult(
            passed=False,
            gate_name=GATE_NAME_TEST_SUITE_COLLECT,
            diagnostics=[f"pytest --collect-only failed: {e}"],
            diagnostic_kind=DiagnosticKind.TEST_COLLECT,
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
            diagnostic_kind=DiagnosticKind.MISSING_ARTIFACT,
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
                    diagnostic_kind=DiagnosticKind.IMPL_MYPY,
                )
            if result.returncode != 0:
                if "No module named mypy" in result.stderr:
                    return GateResult(
                        passed=False,
                        gate_name=GATE_NAME_IMPLEMENTATION_MYPY,
                        diagnostics=["mypy not installed"],
                        diagnostic_kind=DiagnosticKind.TOOL_NOT_FOUND,
                    )
                lines = result.stdout.strip().splitlines()
                diagnostics = lines[:10] if lines else ["mypy reported errors"]
                return GateResult(
                    passed=False,
                    gate_name=GATE_NAME_IMPLEMENTATION_MYPY,
                    diagnostics=diagnostics,
                    diagnostic_kind=DiagnosticKind.IMPL_MYPY,
                )
    except Exception as e:
        return GateResult(
            passed=False,
            gate_name=GATE_NAME_IMPLEMENTATION_MYPY,
            diagnostics=[f"mypy invocation failed: {e}"],
            diagnostic_kind=DiagnosticKind.IMPL_MYPY,
        )
    return GateResult(passed=True, gate_name=GATE_NAME_IMPLEMENTATION_MYPY)


def _run_pytest(
    artifact_path: Path,
    test_suite_path: Path,
    dependency_pyi_paths: list[tuple[str, Path]] | None = None,
    dependency_spec_paths: list[tuple[str, Path]] | None = None,
    python_executable: str | None = None,
    timeout: int | None = None,
    interface_pyi_path: Path | None = None,
    implementation_name: str | None = None,
    gate_name: str = GATE_NAME_IMPLEMENTATION_PYTEST,
) -> GateResult:
    """Run pytest in an isolated tmpdir with dependency stubs.

    Canonical implementation shared by gate, pre_gate, and mutation_gate.
    Callers pass ``gate_name`` to control the GateResult label.
    """
    exe = python_executable or sys.executable
    if timeout is None:
        timeout = GateTimeouts.pytest_timeout
    try:
        with tempfile.TemporaryDirectory(prefix=TEMPFILE_PREFIX_PYTEST) as tmpdir:
            impl_content = artifact_path.read_text()
            impl_name = implementation_name or artifact_path.name
            impl_copy = Path(tmpdir) / impl_name
            impl_copy.write_text(impl_content)
            if artifact_path.stem != ARTIFACT_FILENAME_INTERFACE:
                iface_copy = Path(tmpdir) / f"interface{artifact_path.suffix}"
                iface_copy.write_text(impl_content)
            if interface_pyi_path is not None and interface_pyi_path.exists():
                stub_copy = Path(tmpdir) / "interface.pyi"
                stub_copy.write_text(interface_pyi_path.read_text())
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
                    "-o",
                    "asyncio_mode=auto",
                ],
                cwd=Path(tmpdir),
                env=gate_subprocess_env(PYTHONPATH=tmpdir),
                timeout_s=timeout,
            )
            if result.timed_out:
                return GateResult(
                    passed=False,
                    gate_name=gate_name,
                    diagnostics=[f"pytest timed out after {timeout}s", "timed_out: True"],
                    diagnostic_kind=DiagnosticKind.IMPL_PYTEST,
                )
            if result.returncode != 0:
                if "No module named pytest" in result.stderr:
                    return GateResult(
                        passed=False,
                        gate_name=gate_name,
                        diagnostics=["pytest not installed"],
                        diagnostic_kind=DiagnosticKind.TOOL_NOT_FOUND,
                    )
                lines = result.stdout.strip().splitlines()
                err_lines = result.stderr.strip().splitlines()
                diagnostics = (lines + err_lines)[-3:] or ["pytest reported failures"]
                return GateResult(
                    passed=False,
                    gate_name=gate_name,
                    diagnostics=diagnostics,
                    diagnostic_kind=DiagnosticKind.IMPL_PYTEST,
                )
    except Exception as e:
        return GateResult(
            passed=False,
            gate_name=gate_name,
            diagnostics=[f"pytest invocation failed: {e}"],
            diagnostic_kind=DiagnosticKind.IMPL_PYTEST,
        )
    return GateResult(passed=True, gate_name=gate_name)


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
            diagnostic_kind=DiagnosticKind.TOOL_NOT_FOUND,
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
                    diagnostic_kind=DiagnosticKind.IMPL_LINT,
                )
            if result.returncode != 0:
                lines = result.stdout.strip().splitlines()
                diagnostics = lines[:10] if lines else ["ruff reported lint issues"]
                return GateResult(
                    passed=False,
                    gate_name=GATE_NAME_IMPLEMENTATION_LINT,
                    diagnostics=diagnostics,
                    diagnostic_kind=DiagnosticKind.IMPL_LINT,
                )
    except Exception as e:
        return GateResult(
            passed=False,
            gate_name=GATE_NAME_IMPLEMENTATION_LINT,
            diagnostics=[f"ruff invocation failed: {e}"],
            diagnostic_kind=DiagnosticKind.IMPL_LINT,
        )
    return GateResult(passed=True, gate_name=GATE_NAME_IMPLEMENTATION_LINT)


# tier: enforce
# precondition: test_author may produce async tests that pass vacuously when
#   asyncio_mode is not enabled — the test coroutine object is never awaited,
#   so no assertions execute and pytest reports a pass (dep-v1-364).
# audit trigger: re-evaluate if pytest-asyncio's default mode changes or if
#   the test author prompt guarantees @pytest.mark.asyncio coverage.
def _run_vacuous_test_check(
    artifact_path: Path,
    interface_ref_pyi_path: Path | None = None,
    dependency_pyi_paths: list[tuple[str, Path]] | None = None,
    dependency_spec_paths: list[tuple[str, Path]] | None = None,
    python_executable: str | None = None,
    timeout: int = 60,
) -> GateResult:
    """Run the test suite against a stub implementation (raise NotImplementedError).

    dep-v1-364 invariant: a test that passes against an unimplemented stub is
    vacuous.  This function runs the test suite in a tempdir where the
    interface module is a pure-stub (.pyi → .py with ``raise NotImplementedError``
    bodies).  If pytest reports **all tests passed**, the suite is vacuous.
    If any test fails (which it should against a stub), the suite is non-vacuous.
    """
    from factory.pre_gate import _stub_content_to_py

    exe = python_executable or sys.executable
    try:
        with tempfile.TemporaryDirectory(prefix="sf2_vacuous_") as tmpdir:
            test_copy = Path(tmpdir) / artifact_path.name
            test_copy.write_text(artifact_path.read_text())
            if interface_ref_pyi_path is not None and interface_ref_pyi_path.exists():
                stub_content = interface_ref_pyi_path.read_text()
                stub_py = Path(tmpdir) / "interface.py"
                stub_py.write_text(_stub_content_to_py(stub_content))
            copy_dependency_pyis(tmpdir, dependency_pyi_paths, dependency_spec_paths)
            (Path(tmpdir) / "pyproject.toml").write_text(
                "[tool.pytest.ini_options]\nasyncio_mode = 'auto'\n"
            )
            result = run_subprocess(
                cmd=[
                    exe,
                    "-m",
                    "pytest",
                    str(test_copy),
                    "--tb=line",
                    "-q",
                    "-o",
                    "asyncio_mode=auto",
                ],
                cwd=Path(tmpdir),
                env=gate_subprocess_env(PYTHONPATH=tmpdir),
                timeout_s=timeout,
            )
            if result.timed_out:
                return GateResult(
                    passed=False,
                    gate_name=GATE_NAME_VACUOUS_TEST,
                    diagnostics=[f"Vacuous-test check timed out after {timeout}s"],
                    diagnostic_kind=DiagnosticKind.VACUOUS_TEST,
                )
            if result.returncode == 0:
                out = result.stdout.strip()
                passing_lines = [ln for ln in out.splitlines() if " passed" in ln]
                summary = passing_lines[-1] if passing_lines else out[:200]
                return GateResult(
                    passed=False,
                    gate_name=GATE_NAME_VACUOUS_TEST,
                    diagnostics=[
                        "Test suite passes against stub implementation (all tests vacuous)",
                        f"pytest summary: {summary}",
                        "Tests must fail against raise-NotImplementedError stubs to be valid",
                    ],
                    diagnostic_kind=DiagnosticKind.VACUOUS_TEST,
                )
    except Exception as e:
        return GateResult(
            passed=False,
            gate_name=GATE_NAME_VACUOUS_TEST,
            diagnostics=[f"Vacuous-test check failed: {e}"],
            diagnostic_kind=DiagnosticKind.VACUOUS_TEST,
        )
    return GateResult(passed=True, gate_name=GATE_NAME_VACUOUS_TEST)
