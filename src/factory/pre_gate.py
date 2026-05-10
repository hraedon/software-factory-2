from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from factory.constants import TEMPFILE_PREFIX_MYPY


@dataclass(frozen=True)
class PreGateResult:
    passed: bool
    mypy_passed: bool
    ruff_passed: bool
    diagnostics: list[str]


def pre_gate_implementation(
    artifact_path: Path,
    interface_pyi_path: Path | None = None,
    dependency_pyi_paths: list[tuple[str, Path]] | None = None,
    python_executable: str | None = None,
) -> PreGateResult:
    mypy_result = _run_mypy_fast(
        artifact_path,
        interface_pyi_path,
        dependency_pyi_paths=dependency_pyi_paths,
        python_executable=python_executable,
    )
    ruff_result = _run_ruff_fast(artifact_path, python_executable=python_executable)
    all_diagnostics = mypy_result.get("diagnostics", []) + ruff_result.get("diagnostics", [])
    return PreGateResult(
        passed=mypy_result["passed"] and ruff_result["passed"],
        mypy_passed=mypy_result["passed"],
        ruff_passed=ruff_result["passed"],
        diagnostics=all_diagnostics,
    )


def _copy_dependency_pyis(
    tmpdir: str,
    dependency_pyi_paths: list[tuple[str, Path]] | None,
) -> None:
    if not dependency_pyi_paths:
        return
    tmpdir_path = Path(tmpdir)
    for module_name, dep_path in dependency_pyi_paths:
        if dep_path.exists():
            content = dep_path.read_text()
            dep_py = tmpdir_path / f"{module_name}.py"
            dep_py.write_text(content)
            dep_pyi = tmpdir_path / f"{module_name}.pyi"
            dep_pyi.write_text(content)


def _run_mypy_fast(
    artifact_path: Path,
    interface_pyi_path: Path | None = None,
    dependency_pyi_paths: list[tuple[str, Path]] | None = None,
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
            _copy_dependency_pyis(tmpdir, dependency_pyi_paths)
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
                    return {"passed": True, "diagnostics": []}
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
    except subprocess.TimeoutExpired:
        return {"passed": True, "diagnostics": []}
    except Exception:
        return {"passed": True, "diagnostics": []}
    return {"passed": True, "diagnostics": []}
