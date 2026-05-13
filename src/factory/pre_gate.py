from __future__ import annotations

import ast
import difflib
import logging
import os
import re
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

_IMPORT_FEEDBACK_KIND_DOTTED_SUBMODULE = "dotted_submodule"
_IMPORT_FEEDBACK_KIND_WRONG_MODULE_NAME = "wrong_module_name"
_IMPORT_FEEDBACK_KIND_OTHER = "other_traceback"

_DEFAULT_TIMEOUTS = GateTimeouts()

_PYTEST_DIAGNOSTIC_CHAR_LIMIT = 300
_RAW_OUTPUT_CHAR_LIMIT = 5000

_pre_gate_log = logging.getLogger("factory.pre_gate")


@dataclass(frozen=True)
class GateScope:
    strict_imports: bool = True


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
    imports_symbols_passed: bool
    diagnostics: list[str]
    output: str = ""
    skipped_import_patterns: dict[str, int] | None = None
    import_feedback_kind: str = ""
    import_feedback: str = ""


def validate_artifact_imports(
    artifact_path: Path,
    export_map: dict[str, set[str]],
    scope: GateScope | None = None,
) -> tuple[bool, list[str], dict[str, int]]:
    """AST-only symbol-membership check. Complements the runtime importlib check.

    Walks every ``ast.ImportFrom`` node, cross-references against the
    pre-computed export map, and reports ALL mismatches (not just the first).
    """
    _scope = scope or GateScope()
    skipped: dict[str, int] = {}
    if export_map is None or not artifact_path.exists():
        return True, [], skipped

    content = artifact_path.read_text()
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return True, [], skipped

    mismatches: dict[str, list[tuple[int, list[str]]]] = {}
    type_checking_nodes: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.If):
            test = node.test
            if isinstance(test, ast.Name) and test.id == "TYPE_CHECKING":
                for child in ast.walk(node):
                    type_checking_nodes.add(id(child))

    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        if id(node) in type_checking_nodes:
            skipped["type_checking_block"] = skipped.get("type_checking_block", 0) + 1
            _pre_gate_log.warning(
                "unsupported_import_pattern pattern=type_checking_block module=%s file=%s",
                node.module or "",
                artifact_path,
            )
            continue
        module_name = node.module or ""
        if node.level and node.level > 0:
            skipped["relative"] = skipped.get("relative", 0) + 1
            _pre_gate_log.warning(
                "unsupported_import_pattern pattern=relative module=%s file=%s",
                module_name or ".",
                artifact_path,
            )
            continue
        if "." in module_name:
            skipped["submodule_dotted"] = skipped.get("submodule_dotted", 0) + 1
            _pre_gate_log.warning(
                "unsupported_import_pattern pattern=submodule_dotted module=%s file=%s",
                module_name,
                artifact_path,
            )
            continue
        if module_name not in export_map:
            continue
        if node.names and any(alias.name == "*" for alias in node.names):
            skipped["star"] = skipped.get("star", 0) + 1
            _pre_gate_log.warning(
                "unsupported_import_pattern pattern=star module=%s file=%s",
                module_name,
                artifact_path,
            )
            continue
        available = export_map[module_name]
        unknown = [alias.name for alias in node.names if alias.name not in available]
        if unknown:
            entry = mismatches.setdefault(module_name, [])
            entry.append((node.lineno, unknown))

    if not mismatches:
        return True, [], skipped

    diagnostics = []
    for mod in sorted(mismatches):
        for lineno, names in mismatches[mod]:
            available_sorted = sorted(export_map[mod])
            diagnostics.append(
                f"{artifact_path.name}:{lineno}: '{mod}' imports the following "
                f"unknown symbols: {', '.join(sorted(names))}"
            )
            diagnostics.append(f"  available in {mod}: {', '.join(available_sorted)}")
    return False, diagnostics, skipped


def pre_gate_implementation(
    artifact_path: Path,
    interface_pyi_path: Path | None = None,
    dependency_pyi_paths: list[tuple[str, Path]] | None = None,
    dependency_spec_paths: list[tuple[str, Path]] | None = None,
    python_executable: str | None = None,
    test_suite_path: Path | None = None,
    timeouts: GateTimeouts | None = None,
    export_map: dict[str, set[str]] | None = None,
    gate_scope: GateScope | None = None,
) -> PreGateResult:
    t = timeouts or _DEFAULT_TIMEOUTS
    if not artifact_path.exists():
        return PreGateResult(
            passed=False,
            mypy_passed=True,
            ruff_passed=True,
            pytest_passed=True,
            imports_symbols_passed=True,
            diagnostics=[f"Artifact not found: {artifact_path}"],
        )

    if export_map:
        imports_ok, imports_diags, skipped = validate_artifact_imports(
            artifact_path, export_map, gate_scope
        )
    else:
        imports_ok, imports_diags, skipped = True, [], {}
    if not imports_ok:
        return PreGateResult(
            passed=False,
            mypy_passed=True,
            ruff_passed=True,
            pytest_passed=True,
            imports_symbols_passed=False,
            diagnostics=_truncate_diagnostics(imports_diags),
            skipped_import_patterns=skipped or None,
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
            imports_symbols_passed=True,
            diagnostics=_truncate_diagnostics(all_diagnostics),
            output=mypy_result.get("raw_output", ""),
            skipped_import_patterns=skipped or None,
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
            imports_symbols_passed=True,
            diagnostics=_truncate_diagnostics(all_diagnostics),
            output=ruff_result.get("raw_output", ""),
            skipped_import_patterns=skipped or None,
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
        imports_symbols_passed=True,
        diagnostics=_truncate_diagnostics(all_diagnostics),
        output=pytest_result.get("raw_output", "") if not pytest_result["passed"] else "",
        skipped_import_patterns=skipped or None,
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
            imports_symbols_passed=True,
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
            imports_symbols_passed=True,
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
            imports_symbols_passed=True,
            diagnostics=_truncate_diagnostics(import_result.get("diagnostics", [])),
            output=import_result.get("raw_output", ""),
            import_feedback_kind=import_result.get("import_feedback_kind", ""),
            import_feedback=import_result.get("import_feedback", ""),
        )

    return PreGateResult(
        passed=True,
        mypy_passed=True,
        ruff_passed=True,
        pytest_passed=True,
        imports_symbols_passed=True,
        diagnostics=[],
    )


def pre_gate_test_suite(
    artifact_path: Path,
    interface_pyi_path: Path | None = None,
    dependency_pyi_paths: list[tuple[str, Path]] | None = None,
    dependency_spec_paths: list[tuple[str, Path]] | None = None,
    python_executable: str | None = None,
    timeouts: GateTimeouts | None = None,
    export_map: dict[str, set[str]] | None = None,
    gate_scope: GateScope | None = None,
) -> PreGateResult:
    t = timeouts or _DEFAULT_TIMEOUTS
    if not artifact_path.exists():
        return PreGateResult(
            passed=False,
            mypy_passed=True,
            ruff_passed=True,
            pytest_passed=True,
            imports_symbols_passed=True,
            diagnostics=[f"Artifact not found: {artifact_path}"],
        )

    if export_map:
        imports_ok, imports_diags, skipped = validate_artifact_imports(
            artifact_path, export_map, gate_scope
        )
    else:
        imports_ok, imports_diags, skipped = True, [], {}
    if not imports_ok:
        return PreGateResult(
            passed=False,
            mypy_passed=True,
            ruff_passed=True,
            pytest_passed=True,
            imports_symbols_passed=False,
            diagnostics=_truncate_diagnostics(imports_diags),
            skipped_import_patterns=skipped or None,
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
            imports_symbols_passed=True,
            diagnostics=_truncate_diagnostics(ruff_result.get("diagnostics", [])),
            output=ruff_result.get("raw_output", ""),
            skipped_import_patterns=skipped or None,
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
            imports_symbols_passed=True,
            diagnostics=_truncate_diagnostics(collect_result.get("diagnostics", [])),
            output=collect_result.get("raw_output", ""),
            skipped_import_patterns=skipped or None,
        )

    return PreGateResult(
        passed=True,
        mypy_passed=True,
        ruff_passed=True,
        pytest_passed=True,
        imports_symbols_passed=True,
        diagnostics=[],
        skipped_import_patterns=skipped or None,
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


def _parse_import_failure(
    stderr: str,
    artifact_lines: list[str] | None = None,
    available_modules: list[str] | None = None,
) -> tuple[str, str]:
    """Parse import-check stderr into a feedback kind and actionable message.

    Returns (feedback_kind, feedback_message) where feedback_kind is one of
    IMPORT_FEEDBACK_KIND_DOTTED_SUBMODULE, IMPORT_FEEDBACK_KIND_WRONG_MODULE_NAME,
    or IMPORT_FEEDBACK_KIND_OTHER.

    The feedback_message is intended for model retry context and must stay under
    500 characters.
    """
    module_not_found_match = re.search(
        r"ModuleNotFoundError:\s*No module named ['\"](.+?)['\"]", stderr
    )
    import_error_match = re.search(
        r"ImportError:\s*(?:cannot import name .+? from ['\"](.+?)['\"]|.+)",
        stderr,
    )

    unavailable_modules = sorted(available_modules) if available_modules else []

    def _suggest(module_name: str) -> str:
        if not unavailable_modules:
            return ""
        best = max(
            unavailable_modules,
            key=lambda m: difflib.SequenceMatcher(None, m, module_name).ratio(),
        )
        ratio = difflib.SequenceMatcher(None, best, module_name).ratio()
        if ratio >= 0.4:
            return f"\nDid you mean: {best}?"
        return ""

    if module_not_found_match:
        missing = module_not_found_match.group(1)
        if "." in missing:
            top = missing.split(".")[0]
            msg = (
                f"Import resolution failed: '{missing}' is a dotted submodule path.\n"
                f"Dotted submodule imports (from a.b import c) are not supported — "
                f"dependencies are injected as flat modules by the pipeline.\n"
                f"Use: from {top} import ..."
            )
            if unavailable_modules:
                msg += f"\nAvailable flat modules: {', '.join(unavailable_modules)}"
            return _IMPORT_FEEDBACK_KIND_DOTTED_SUBMODULE, msg[:500]
        line_info = _find_import_line(artifact_lines, missing)
        msg = f"Import resolution failed{line_info}: module '{missing}' not found."
        if unavailable_modules:
            msg += f"\nAvailable modules: {', '.join(unavailable_modules)}"
        msg += _suggest(missing)
        return _IMPORT_FEEDBACK_KIND_WRONG_MODULE_NAME, msg[:500]

    if import_error_match:
        from_module = import_error_match.group(1)
        if from_module and "." in from_module:
            top = from_module.split(".")[0]
            msg = (
                f"Import resolution failed: '{from_module}' is a dotted submodule path.\n"
                f"Dotted submodule imports are not supported — "
                f"dependencies are injected as flat modules by the pipeline.\n"
                f"Use: from {top} import ..."
            )
            if unavailable_modules:
                msg += f"\nAvailable flat modules: {', '.join(unavailable_modules)}"
            return _IMPORT_FEEDBACK_KIND_DOTTED_SUBMODULE, msg[:500]

    lines = stderr.strip().splitlines()
    diags = lines[:3] if lines else ["import check failed"]
    return _IMPORT_FEEDBACK_KIND_OTHER, "; ".join(diags)[:500]


def _find_import_line(artifact_lines: list[str] | None, module_name: str) -> str:
    if artifact_lines is None:
        return ""
    for i, line in enumerate(artifact_lines, 1):
        stripped = line.strip()
        if stripped.startswith("import ") and module_name in stripped:
            return f" at line {i}"
        if stripped.startswith("from ") and module_name in stripped:
            return f" at line {i}"
    return ""


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
                artifact_lines = None
                try:
                    artifact_lines = artifact_path.read_text().splitlines()
                except Exception:
                    pass
                available_modules = (
                    [name for name, _ in dependency_pyi_paths] if dependency_pyi_paths else []
                )
                feedback_kind, feedback_msg = _parse_import_failure(
                    result.stderr,
                    artifact_lines=artifact_lines,
                    available_modules=available_modules,
                )
                return {
                    **_fail(diags, _truncate_raw_output(result.stderr)),
                    "import_feedback_kind": feedback_kind,
                    "import_feedback": feedback_msg,
                }
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
