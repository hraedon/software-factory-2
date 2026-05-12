from __future__ import annotations

import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import NamedTuple

from factory.config import GateTimeouts
from factory.constants import (
    ARTIFACT_FILENAME_INTERFACE,
    INNER_GATE_RUFF_IGNORE,
    INNER_GATE_RUFF_SELECT,
    INNER_GATE_RUFF_UNSAFE_FIXES,
    TEMPFILE_PREFIX_COLLECT,
    TEMPFILE_PREFIX_MYPY,
    TEMPFILE_PREFIX_PYTEST,
)

_DEFAULT_TIMEOUTS = GateTimeouts()

_PYTEST_DIAGNOSTIC_CHAR_LIMIT = 300
_RAW_OUTPUT_CHAR_LIMIT = 5000


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
    output: str = ""


def pre_gate_implementation(
    artifact_path: Path,
    interface_pyi_path: Path | None = None,
    dependency_pyi_paths: list[tuple[str, Path]] | None = None,
    dependency_spec_paths: list[tuple[str, Path]] | None = None,
    python_executable: str | None = None,
    test_suite_path: Path | None = None,
    timeouts: GateTimeouts | None = None,
) -> PreGateResult:
    t = timeouts or _DEFAULT_TIMEOUTS
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
        timeout=t.mypy_timeout,
    )
    if not mypy_result["passed"]:
        all_diagnostics = mypy_result.get("diagnostics", [])
        return PreGateResult(
            passed=False,
            mypy_passed=False,
            ruff_passed=True,
            pytest_passed=True,
            diagnostics=_truncate_diagnostics(all_diagnostics),
            output=mypy_result.get("raw_output", ""),
        )

    ruff_result = _run_ruff_fast(
        artifact_path, python_executable=python_executable, timeout=t.ruff_timeout
    )
    if not ruff_result["passed"]:
        all_diagnostics = mypy_result.get("diagnostics", []) + ruff_result.get("diagnostics", [])
        return PreGateResult(
            passed=False,
            mypy_passed=True,
            ruff_passed=False,
            pytest_passed=True,
            diagnostics=_truncate_diagnostics(all_diagnostics),
            output=ruff_result.get("raw_output", ""),
        )

    pytest_result = _run_pytest_fast(
        artifact_path,
        interface_pyi_path=interface_pyi_path,
        dependency_pyi_paths=dependency_pyi_paths,
        dependency_spec_paths=dependency_spec_paths,
        python_executable=python_executable,
        test_suite_path=test_suite_path,
        timeout=t.pytest_timeout,
    )
    all_diagnostics = ruff_result.get("diagnostics", []) + pytest_result.get("diagnostics", [])
    return PreGateResult(
        passed=mypy_result["passed"] and ruff_result["passed"] and pytest_result["passed"],
        mypy_passed=True,
        ruff_passed=True,
        pytest_passed=pytest_result["passed"],
        diagnostics=_truncate_diagnostics(all_diagnostics),
        output=pytest_result.get("raw_output", "") if not pytest_result["passed"] else "",
    )


def pre_gate_interface_spec(
    artifact_path: Path,
    dependency_pyi_paths: list[tuple[str, Path]] | None = None,
    python_executable: str | None = None,
    timeouts: GateTimeouts | None = None,
) -> PreGateResult:
    t = timeouts or _DEFAULT_TIMEOUTS
    if not artifact_path.exists():
        return PreGateResult(
            passed=False,
            mypy_passed=True,
            ruff_passed=True,
            pytest_passed=True,
            diagnostics=[f"Artifact not found: {artifact_path}"],
        )

    ruff_result = _run_ruff_fast(
        artifact_path, python_executable=python_executable, timeout=t.ruff_timeout
    )
    if not ruff_result["passed"]:
        return PreGateResult(
            passed=False,
            mypy_passed=True,
            ruff_passed=False,
            pytest_passed=True,
            diagnostics=_truncate_diagnostics(ruff_result.get("diagnostics", [])),
            output=ruff_result.get("raw_output", ""),
        )

    import_result = _run_import_check(
        artifact_path,
        dependency_pyi_paths=dependency_pyi_paths,
        python_executable=python_executable,
        timeout=t.import_timeout,
    )
    if not import_result["passed"]:
        return PreGateResult(
            passed=False,
            mypy_passed=True,
            ruff_passed=True,
            pytest_passed=True,
            diagnostics=_truncate_diagnostics(import_result.get("diagnostics", [])),
            output=import_result.get("raw_output", ""),
        )

    return PreGateResult(
        passed=True,
        mypy_passed=True,
        ruff_passed=True,
        pytest_passed=True,
        diagnostics=[],
    )


def pre_gate_test_suite(
    artifact_path: Path,
    interface_pyi_path: Path | None = None,
    dependency_pyi_paths: list[tuple[str, Path]] | None = None,
    dependency_spec_paths: list[tuple[str, Path]] | None = None,
    python_executable: str | None = None,
    timeouts: GateTimeouts | None = None,
) -> PreGateResult:
    t = timeouts or _DEFAULT_TIMEOUTS
    if not artifact_path.exists():
        return PreGateResult(
            passed=False,
            mypy_passed=True,
            ruff_passed=True,
            pytest_passed=True,
            diagnostics=[f"Artifact not found: {artifact_path}"],
        )

    ruff_result = _run_ruff_fast(
        artifact_path, python_executable=python_executable, timeout=t.ruff_timeout
    )
    if not ruff_result["passed"]:
        return PreGateResult(
            passed=False,
            mypy_passed=True,
            ruff_passed=False,
            pytest_passed=True,
            diagnostics=_truncate_diagnostics(ruff_result.get("diagnostics", [])),
            output=ruff_result.get("raw_output", ""),
        )

    collect_result = _run_collect_only(
        artifact_path,
        interface_pyi_path=interface_pyi_path,
        dependency_pyi_paths=dependency_pyi_paths,
        dependency_spec_paths=dependency_spec_paths,
        python_executable=python_executable,
        timeout=t.collect_timeout,
    )
    if not collect_result["passed"]:
        return PreGateResult(
            passed=False,
            mypy_passed=True,
            ruff_passed=True,
            pytest_passed=False,
            diagnostics=_truncate_diagnostics(collect_result.get("diagnostics", [])),
            output=collect_result.get("raw_output", ""),
        )

    return PreGateResult(
        passed=True,
        mypy_passed=True,
        ruff_passed=True,
        pytest_passed=True,
        diagnostics=[],
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


def _truncate_raw_output(text: str, limit: int = _RAW_OUTPUT_CHAR_LIMIT) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]


def _fail(
    diagnostics: list[str],
    raw_output: str = "",
) -> dict:
    return {"passed": False, "diagnostics": diagnostics, "raw_output": raw_output}


def _ok() -> dict:
    return {"passed": True, "diagnostics": [], "raw_output": ""}


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


def _run_import_check(
    artifact_path: Path,
    dependency_pyi_paths: list[tuple[str, Path]] | None = None,
    python_executable: str | None = None,
    timeout: int = 60,
) -> dict:
    import tempfile

    exe = python_executable or sys.executable
    module_stem = artifact_path.stem
    if not module_stem.isidentifier():
        return _fail([f"Invalid module name '{module_stem}' for import check"])
    try:
        with tempfile.TemporaryDirectory(prefix="sf2_import_") as tmpdir:
            module_copy = Path(tmpdir) / f"{module_stem}.py"
            module_copy.write_text(artifact_path.read_text())
            copy_dependency_pyis(tmpdir, dependency_pyi_paths)
            result = subprocess.run(
                [exe, "-c", f"import {module_stem}"],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=tmpdir,
                env={**os.environ, "PYTHONPATH": tmpdir},
            )
            if result.returncode != 0:
                lines = result.stderr.strip().splitlines()
                diags = lines[:5] if lines else ["import check failed"]
                return _fail(diags, _truncate_raw_output(result.stderr))
    except subprocess.TimeoutExpired:
        return _fail([f"import check timed out after {timeout}s"])
    except Exception as e:
        return _fail([f"import check failed: {e}"])
    return _ok()


def _run_collect_only(
    artifact_path: Path,
    interface_pyi_path: Path | None = None,
    dependency_pyi_paths: list[tuple[str, Path]] | None = None,
    dependency_spec_paths: list[tuple[str, Path]] | None = None,
    python_executable: str | None = None,
    timeout: int = 120,
) -> dict:
    import tempfile

    exe = python_executable or sys.executable
    try:
        with tempfile.TemporaryDirectory(prefix=TEMPFILE_PREFIX_COLLECT) as tmpdir:
            test_copy = Path(tmpdir) / artifact_path.name
            test_copy.write_text(artifact_path.read_text())
            if interface_pyi_path is not None and interface_pyi_path.exists():
                stub_copy = Path(tmpdir) / "interface.pyi"
                stub_copy.write_text(interface_pyi_path.read_text())
                iface_py = Path(tmpdir) / "interface.py"
                iface_py.write_text(interface_pyi_path.read_text())
            copy_dependency_pyis(tmpdir, dependency_pyi_paths, dependency_spec_paths)
            result = subprocess.run(
                [exe, "-m", "pytest", "--collect-only", "-q", str(test_copy)],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=tmpdir,
                env={**os.environ, "PYTHONPATH": tmpdir},
            )
            if result.returncode != 0:
                if "No module named pytest" in result.stderr:
                    return _fail(["pytest not installed"])
                lines = result.stderr.strip().splitlines()
                out_lines = result.stdout.strip().splitlines()
                combined = out_lines + lines
                diags = combined[:5] if combined else ["pytest collect-only failed"]
                raw = _truncate_raw_output(result.stdout + "\n" + result.stderr)
                return _fail(diags, raw)
    except subprocess.TimeoutExpired:
        return _fail([f"pytest collect-only timed out after {timeout}s"])
    except Exception as e:
        return _fail([f"pytest collect-only failed: {e}"])
    return _ok()


def _run_mypy_fast(
    artifact_path: Path,
    interface_pyi_path: Path | None = None,
    dependency_pyi_paths: list[tuple[str, Path]] | None = None,
    dependency_spec_paths: list[tuple[str, Path]] | None = None,
    python_executable: str | None = None,
    timeout: int = 120,
) -> dict:
    import tempfile

    exe = python_executable or sys.executable
    if interface_pyi_path is None or not interface_pyi_path.exists():
        return _ok()
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
                timeout=timeout,
                cwd=tmpdir,
                env={**os.environ, "MYPYPATH": tmpdir},
            )
            if result.returncode != 0:
                if "No module named mypy" in result.stderr:
                    return _fail(["mypy not installed"])
                lines = result.stdout.strip().splitlines()
                diags = lines[:10] if lines else ["mypy reported errors"]
                return _fail(diags, _truncate_raw_output(result.stdout))
    except subprocess.TimeoutExpired:
        return _fail([f"mypy timed out after {timeout}s"])
    except Exception as e:
        return _fail([f"mypy invocation failed: {e}"])
    return _ok()


_RAW_ARTIFACT_SUFFIX = ".orig"


def _run_ruff_fast(
    artifact_path: Path,
    python_executable: str | None = None,
    timeout: int = 60,
) -> dict:
    import tempfile

    exe = python_executable or sys.executable
    check_args = ["--select", INNER_GATE_RUFF_SELECT, "--ignore", INNER_GATE_RUFF_IGNORE]
    original_content = artifact_path.read_text()
    try:
        with tempfile.TemporaryDirectory(prefix="sf2_ruff_") as tmpdir:
            tmp_copy = Path(tmpdir) / artifact_path.name
            tmp_copy.write_text(original_content)
            subprocess.run(
                [
                    exe,
                    "-m",
                    "ruff",
                    "check",
                    "--fix",
                    "--unsafe-fixes",
                    "--select",
                    INNER_GATE_RUFF_UNSAFE_FIXES,
                    str(tmp_copy),
                ],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            subprocess.run(
                [exe, "-m", "ruff", "check", "--fix", *check_args, str(tmp_copy)],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            subprocess.run(
                [exe, "-m", "ruff", "format", str(tmp_copy)],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            result = subprocess.run(
                [exe, "-m", "ruff", "check", *check_args, str(tmp_copy)],
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            if result.returncode != 0:
                lines = result.stdout.strip().splitlines()
                diags = lines[:10] if lines else ["ruff check reported errors"]
                return _fail(diags, _truncate_raw_output(result.stdout))
            fixed_content = tmp_copy.read_text()
            if fixed_content != original_content:
                orig_backup = artifact_path.parent / f".{artifact_path.name}{_RAW_ARTIFACT_SUFFIX}"
                orig_backup.write_text(original_content)
                artifact_path.write_text(fixed_content)
    except subprocess.TimeoutExpired:
        return _fail([f"ruff timed out after {timeout}s"])
    except Exception as e:
        return _fail([f"ruff invocation failed: {e}"])
    return _ok()


def _run_pytest_fast(
    artifact_path: Path,
    interface_pyi_path: Path | None = None,
    dependency_pyi_paths: list[tuple[str, Path]] | None = None,
    dependency_spec_paths: list[tuple[str, Path]] | None = None,
    python_executable: str | None = None,
    test_suite_path: Path | None = None,
    timeout: int = 300,
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
                timeout=timeout,
                cwd=tmpdir,
                env={
                    **os.environ,
                    "PYTHONPATH": tmpdir,
                },
            )
            if result.returncode != 0:
                if "No module named pytest" in result.stderr:
                    return _fail(["pytest not installed"])
                lines = result.stdout.strip().splitlines()
                err_lines = result.stderr.strip().splitlines()
                combined = lines + err_lines
                diags = combined[-3:] if combined else ["pytest reported failures"]
                raw = _truncate_raw_output(result.stdout + "\n" + result.stderr)
                return _fail(diags, raw)
    except subprocess.TimeoutExpired:
        return _fail([f"pytest timed out after {timeout}s"])
    except Exception as e:
        return _fail([f"pytest invocation failed: {e}"])
    return _ok()
