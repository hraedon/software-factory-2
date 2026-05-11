from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

from factory.constants import (
    ARTIFACT_FILENAME_INTERFACE,
    TEMPFILE_PREFIX_MYPY,
    TEMPFILE_PREFIX_PYTEST,
)

_PYTEST_DIAGNOSTIC_CHAR_LIMIT = 300


class PreGateDeps(NamedTuple):
    interface_pyi_path: Path | None
    dep_paths: list[tuple[str, Path]] | None
    dep_spec_paths: list[tuple[str, Path]] | None = None
    python_executable: str | None = None
    test_suite_path: Path | None = None


@dataclass(frozen=True)
class PreGateResult:
    passed: bool
    mypy_passed: bool
    ruff_passed: bool
    pytest_passed: bool
    diagnostics: list[str]


def pre_gate_implementation(
    artifact_path: Path,
    interface_pyi_path: Path | None = None,
    dependency_pyi_paths: list[tuple[str, Path]] | None = None,
    dependency_spec_paths: list[tuple[str, Path]] | None = None,
    python_executable: str | None = None,
    test_suite_path: Path | None = None,
) -> PreGateResult:
    if not artifact_path.exists():
        return PreGateResult(
            passed=False,
            mypy_passed=True,
            ruff_passed=True,
            pytest_passed=True,
            diagnostics=[f"Artifact not found: {artifact_path}"],
        )

    mypy_result = _run_mypy_fast(
        artifact_path,
        interface_pyi_path,
        dependency_pyi_paths=dependency_pyi_paths,
        dependency_spec_paths=dependency_spec_paths,
        python_executable=python_executable,
    )
    if not mypy_result["passed"]:
        all_diagnostics = mypy_result.get("diagnostics", [])
        return PreGateResult(
            passed=False,
            mypy_passed=False,
            ruff_passed=True,
            pytest_passed=True,
            diagnostics=_truncate_diagnostics(all_diagnostics),
        )

    ruff_result = _run_ruff_fast(artifact_path, python_executable=python_executable)
    if not ruff_result["passed"]:
        all_diagnostics = mypy_result.get("diagnostics", []) + ruff_result.get("diagnostics", [])
        return PreGateResult(
            passed=False,
            mypy_passed=True,
            ruff_passed=False,
            pytest_passed=True,
            diagnostics=_truncate_diagnostics(all_diagnostics),
        )

    pytest_result = _run_pytest_fast(
        artifact_path,
        interface_pyi_path=interface_pyi_path,
        dependency_pyi_paths=dependency_pyi_paths,
        dependency_spec_paths=dependency_spec_paths,
        python_executable=python_executable,
        test_suite_path=test_suite_path,
    )
    all_diagnostics = ruff_result.get("diagnostics", []) + pytest_result.get("diagnostics", [])
    return PreGateResult(
        passed=mypy_result["passed"] and ruff_result["passed"] and pytest_result["passed"],
        mypy_passed=True,
        ruff_passed=True,
        pytest_passed=pytest_result["passed"],
        diagnostics=_truncate_diagnostics(all_diagnostics),
    )


def _truncate_diagnostics(
    diagnostics: list[str],
    char_limit: int = _PYTEST_DIAGNOSTIC_CHAR_LIMIT,
) -> list[str]:
    truncated = []
    for line in diagnostics:
        if len(line) > char_limit:
            truncated.append(line[:char_limit] + "...")
        else:
            truncated.append(line)
    return truncated


def copy_dependency_pyis(
    tmpdir: str,
    dependency_pyi_paths: list[tuple[str, Path]] | None,
    dependency_spec_paths: list[tuple[str, Path]] | None = None,
) -> None:
    if not dependency_pyi_paths and not dependency_spec_paths:
        return
    tmpdir_path = Path(tmpdir)
    spec_map: dict[str, Path] = {}
    if dependency_spec_paths:
        for module_name, spec_path in dependency_spec_paths:
            if spec_path.exists():
                spec_map[module_name] = spec_path
    if not dependency_pyi_paths:
        return
    for module_name, dep_path in dependency_pyi_paths:
        if not dep_path.exists():
            continue
        content = dep_path.read_text()
        dep_py = tmpdir_path / f"{module_name}.py"
        dep_py.write_text(content)
        if module_name in spec_map:
            dep_pyi = tmpdir_path / f"{module_name}.pyi"
            dep_pyi.write_text(spec_map[module_name].read_text())
        else:
            dep_pyi = tmpdir_path / f"{module_name}.pyi"
            dep_pyi.write_text(content)


def _run_mypy_fast(
    artifact_path: Path,
    interface_pyi_path: Path | None = None,
    dependency_pyi_paths: list[tuple[str, Path]] | None = None,
    dependency_spec_paths: list[tuple[str, Path]] | None = None,
    python_executable: str | None = None,
) -> dict:
    import tempfile

    exe = python_executable or sys.executable
    if interface_pyi_path is None or not interface_pyi_path.exists():
        return {"passed": True, "diagnostics": []}
    try:
        with tempfile.TemporaryDirectory(prefix=TEMPFILE_PREFIX_MYPY) as tmpdir:
            impl_copy = Path(tmpdir) / "interface.py"
            impl_copy.write_text(artifact_path.read_text())
            stub_copy = Path(tmpdir) / "interface.pyi"
            stub_copy.write_text(interface_pyi_path.read_text())
            copy_dependency_pyis(tmpdir, dependency_pyi_paths, dependency_spec_paths)
            result = subprocess.run(
                [exe, "-m", "mypy", "--strict", "--no-error-summary", str(impl_copy)],
                capture_output=True,
                text=True,
                timeout=60,
                cwd=tmpdir,
                env={**os.environ, "MYPYPATH": tmpdir},
            )
            if result.returncode != 0:
                if "No module named mypy" in result.stderr:
                    return {"passed": False, "diagnostics": ["mypy not installed"]}
                lines = result.stdout.strip().splitlines()
                diagnostics = lines[:10] if lines else ["mypy reported errors"]
                return {"passed": False, "diagnostics": diagnostics}
    except subprocess.TimeoutExpired:
        return {"passed": False, "diagnostics": ["mypy timed out after 60s"]}
    except Exception as e:
        return {"passed": False, "diagnostics": [f"mypy invocation failed: {e}"]}
    return {"passed": True, "diagnostics": []}


def _run_ruff_fast(
    artifact_path: Path,
    python_executable: str | None = None,
) -> dict:
    exe = python_executable or sys.executable
    try:
        result = subprocess.run(
            [exe, "-m", "ruff", "check", "--fix", str(artifact_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode != 0:
            lines = result.stdout.strip().splitlines()
            diagnostics = lines[:10] if lines else ["ruff check reported errors"]
            return {"passed": False, "diagnostics": diagnostics}
        result2 = subprocess.run(
            [exe, "-m", "ruff", "format", str(artifact_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result2.returncode != 0:
            lines = result2.stderr.strip().splitlines()
            diagnostics = lines[:10] if lines else ["ruff format reported errors"]
            return {"passed": False, "diagnostics": diagnostics}
        result3 = subprocess.run(
            [exe, "-m", "ruff", "check", str(artifact_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result3.returncode != 0:
            lines = result3.stdout.strip().splitlines()
            diagnostics = lines[:10] if lines else ["ruff check reported errors"]
            return {"passed": False, "diagnostics": diagnostics}
    except subprocess.TimeoutExpired:
        return {"passed": False, "diagnostics": ["ruff timed out after 30s"]}
    except Exception as e:
        return {"passed": False, "diagnostics": [f"ruff invocation failed: {e}"]}
    return {"passed": True, "diagnostics": []}


def _run_pytest_fast(
    artifact_path: Path,
    interface_pyi_path: Path | None = None,
    dependency_pyi_paths: list[tuple[str, Path]] | None = None,
    dependency_spec_paths: list[tuple[str, Path]] | None = None,
    python_executable: str | None = None,
    test_suite_path: Path | None = None,
) -> dict:
    import tempfile

    if test_suite_path is None or not test_suite_path.exists():
        return {"passed": True, "diagnostics": []}

    exe = python_executable or sys.executable
    try:
        with tempfile.TemporaryDirectory(prefix=TEMPFILE_PREFIX_PYTEST) as tmpdir:
            impl_content = artifact_path.read_text()
            impl_copy = Path(tmpdir) / artifact_path.name
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
            result = subprocess.run(
                [
                    exe,
                    "-m",
                    "pytest",
                    str(test_copy),
                    "-x",
                    "--tb=short",
                    "-q",
                ],
                capture_output=True,
                text=True,
                timeout=120,
                cwd=tmpdir,
                env={
                    **os.environ,
                    "PYTHONPATH": tmpdir,
                },
            )
            if result.returncode != 0:
                if "No module named pytest" in result.stderr:
                    return {"passed": False, "diagnostics": ["pytest not installed"]}
                lines = result.stdout.strip().splitlines()
                err_lines = result.stderr.strip().splitlines()
                combined = lines + err_lines
                diagnostics = combined[-3:] if combined else ["pytest reported failures"]
                return {"passed": False, "diagnostics": diagnostics}
    except subprocess.TimeoutExpired:
        return {"passed": False, "diagnostics": ["pytest timed out after 120s"]}
    except Exception as e:
        return {"passed": False, "diagnostics": [f"pytest invocation failed: {e}"]}
    return {"passed": True, "diagnostics": []}
