from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

from factory.config import GateTimeouts
from factory.constants import (
    GATE_NAME_INTEGRATION,
    GATE_NAME_INTEGRATION_IMPORT,
    GATE_NAME_INTEGRATION_MYPY,
    GATE_NAME_INTEGRATION_PYTEST,
)
from factory.gate._base import GateResult, _guard_artifact_size
from factory.sandbox import gate_subprocess_env
from factory.subprocess import run as run_subprocess


def evaluate_integration(
    artifact_path: Path,
    python_executable: str | None = None,
    gate_timeouts: GateTimeouts | None = None,
) -> GateResult:
    """Evaluate an integration artifact.

    Expects a JSON object with `assembled_tree` (dict of filename -> source).
    Mechanical gates: import resolution, mypy, pytest on assembled tree.
    """
    t = gate_timeouts or GateTimeouts()
    exe = python_executable or sys.executable

    size_guard = _guard_artifact_size(artifact_path)
    if size_guard is not None:
        return size_guard

    try:
        text = artifact_path.read_text()
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return GateResult(
            passed=False,
            gate_name=GATE_NAME_INTEGRATION_IMPORT,
            diagnostics=[f"Integration artifact is not valid JSON: {exc}"],
            diagnostic_kind="integration_import",
        )
    except Exception as exc:
        return GateResult(
            passed=False,
            gate_name=GATE_NAME_INTEGRATION_IMPORT,
            diagnostics=[f"Failed to read integration artifact: {exc}"],
            diagnostic_kind="integration_import",
        )

    assembled_tree = data.get("assembled_tree")
    if not isinstance(assembled_tree, dict) or not assembled_tree:
        return GateResult(
            passed=False,
            gate_name=GATE_NAME_INTEGRATION_IMPORT,
            diagnostics=["Integration artifact missing 'assembled_tree' field or empty"],
            diagnostic_kind="integration_import",
        )

    with tempfile.TemporaryDirectory(prefix="sf2_integration_") as tmpdir:
        tmp_path = Path(tmpdir).resolve()
        for filename, source in assembled_tree.items():
            if not isinstance(filename, str):
                return GateResult(
                    passed=False,
                    gate_name=GATE_NAME_INTEGRATION_IMPORT,
                    diagnostics=[f"assembled_tree key {filename!r} is not a string"],
                    diagnostic_kind="integration_unsafe_path",
                )
            if Path(filename).is_absolute():
                return GateResult(
                    passed=False,
                    gate_name=GATE_NAME_INTEGRATION_IMPORT,
                    diagnostics=[f"assembled_tree key {filename!r} is absolute"],
                    diagnostic_kind="integration_unsafe_path",
                )
            if ".." in Path(filename).parts:
                return GateResult(
                    passed=False,
                    gate_name=GATE_NAME_INTEGRATION_IMPORT,
                    diagnostics=[f"assembled_tree key {filename!r} contains '..' segment"],
                    diagnostic_kind="integration_unsafe_path",
                )
            dest = tmp_path / filename
            if not dest.resolve().is_relative_to(tmp_path):
                return GateResult(
                    passed=False,
                    gate_name=GATE_NAME_INTEGRATION_IMPORT,
                    diagnostics=[f"assembled_tree key {filename!r} escapes sandbox"],
                    diagnostic_kind="integration_unsafe_path",
                )
            dest.parent.mkdir(parents=True, exist_ok=True)
            try:
                dest.write_text(str(source))
            except Exception as exc:
                return GateResult(
                    passed=False,
                    gate_name=GATE_NAME_INTEGRATION_IMPORT,
                    diagnostics=[f"Failed to write {filename}: {exc}"],
                    diagnostic_kind="integration_import",
                )

        # Mechanical promotion: if the tree contains a top-level __init__.py
        # with relative imports but no directory matching the entry_point package
        # name, promote all top-level items into that package directory.
        entry_point = str(data.get("entry_point", "")).strip()
        if entry_point:
            pkg_name = entry_point.split(".")[0]
            top_init = tmp_path / "__init__.py"
            pkg_dir = tmp_path / pkg_name
            if top_init.exists() and not pkg_dir.exists():
                init_text = top_init.read_text()
                has_relative_import = "from ." in init_text
                if has_relative_import:
                    top_items = [p for p in tmp_path.iterdir() if p.name != pkg_name]
                    if top_items:
                        pkg_dir.mkdir(parents=True, exist_ok=True)
                        for item in top_items:
                            shutil.move(str(item), str(pkg_dir / item.name))
                else:
                    # No-op __init__.py shadows sibling modules for pytest.
                    # Remove it so imports resolve to the sibling files.
                    has_sibling_py = any(
                        p.suffix == ".py" and p.name != "__init__.py" for p in tmp_path.iterdir()
                    )
                    if has_sibling_py:
                        top_init.unlink()

        py_files = sorted(
            tmp_path.rglob("*.py"),
            key=lambda f: (f.name != "__init__.py", str(f)),
        )

        # Gate 1: import resolution (subprocess under gate venv — BC-174)
        _import_check_script = (
            "import importlib.util, json, sys\n"
            "from pathlib import Path\n"
            "tmp = Path(sys.argv[1])\n"
            "sys.path.insert(0, str(tmp))\n"
            "errors = []\n"
            "for pyf in sorted(\n"
            "    tmp.rglob('*.py'),\n"
            "    key=lambda f: (f.name != '__init__.py', str(f)),\n"
            "):\n"
            "    rel = list(pyf.relative_to(tmp).parts)\n"
            "    is_init = rel[-1] == '__init__.py'\n"
            "    mod = '.'.join(rel[:-1]) if is_init else '.'.join(rel)[:-3]\n"
            "    if mod == '__init__':\n"
            "        continue\n"
            "    try:\n"
            "        spec = importlib.util.spec_from_file_location(\n"
            "            mod, pyf,\n"
            "            submodule_search_locations=[str(pyf.parent)] if is_init else None,\n"
            "        )\n"
            "        m = importlib.util.module_from_spec(spec)\n"
            "        sys.modules[mod] = m\n"
            "        spec.loader.exec_module(m)\n"
            "    except Exception as exc:\n"
            "        errors.append(f'{pyf.name}: {exc}')\n"
            "print(json.dumps(errors))\n"
        )
        import_result = run_subprocess(
            cmd=[exe, "-c", _import_check_script, str(tmp_path)],
            cwd=tmp_path,
            env=gate_subprocess_env(PYTHONPATH=str(tmp_path)),
            timeout_s=t.pytest_timeout,
        )
        if import_result.timed_out:
            return GateResult(
                passed=False,
                gate_name=GATE_NAME_INTEGRATION_IMPORT,
                diagnostics=["Import-check subprocess timed out", "timed_out: True"],
                diagnostic_kind="integration_import",
            )
        if import_result.returncode != 0:
            stderr = import_result.stderr.strip()
            return GateResult(
                passed=False,
                gate_name=GATE_NAME_INTEGRATION_IMPORT,
                diagnostics=[
                    "Import-check subprocess crashed",
                    stderr[:500] if stderr else "(no stderr)",
                ],
                diagnostic_kind="integration_import",
            )
        try:
            import_errors = json.loads(import_result.stdout)
        except json.JSONDecodeError as exc:
            return GateResult(
                passed=False,
                gate_name=GATE_NAME_INTEGRATION_IMPORT,
                diagnostics=[
                    f"Import-check output is not valid JSON: {exc}",
                    import_result.stdout[:500],
                ],
                diagnostic_kind="integration_import",
            )
        if import_errors:
            return GateResult(
                passed=False,
                gate_name=GATE_NAME_INTEGRATION_IMPORT,
                diagnostics=[
                    f"Import resolution failed for {len(import_errors)} module(s)",
                    *import_errors[:5],
                ],
                diagnostic_kind="integration_import",
            )

        # Gate 2: mypy on assembled tree
        # BC-175: target the directory (not a file list) so mypy resolves
        #   modules via --explicit-package-bases rather than both the
        #   MYPYPATH and the explicit file path — preventing the
        #   "Source file found twice" collision when __init__.py is present.
        # BC-176: --allow-empty-bodies so ellipsis-body interface stubs
        #   emitted by interface_architect are not rejected by --strict.
        py_files_list = [str(f) for f in py_files]
        if py_files_list:
            mypy_result = run_subprocess(
                cmd=[
                    exe,
                    "-m",
                    "mypy",
                    "--strict",
                    "--no-error-summary",
                    "--explicit-package-bases",
                    "--allow-empty-bodies",
                    str(tmp_path),
                ],
                cwd=tmp_path,
                env=gate_subprocess_env(MYPYPATH=str(tmp_path)),
                timeout_s=t.mypy_timeout,
            )
            if mypy_result.timed_out:
                return GateResult(
                    passed=False,
                    gate_name=GATE_NAME_INTEGRATION_MYPY,
                    diagnostics=[
                        f"mypy timed out after {t.mypy_timeout}s",
                        "timed_out: True",
                    ],
                    diagnostic_kind="integration_mypy",
                )
            if "No module named mypy" in mypy_result.stderr:
                return GateResult(
                    passed=False,
                    gate_name=GATE_NAME_INTEGRATION_MYPY,
                    diagnostics=["mypy not installed"],
                    diagnostic_kind="tool_not_found",
                )
            if mypy_result.returncode != 0:
                lines = mypy_result.stdout.strip().splitlines()
                diagnostics = lines[:10] if lines else ["mypy reported errors on assembled tree"]
                return GateResult(
                    passed=False,
                    gate_name=GATE_NAME_INTEGRATION_MYPY,
                    diagnostics=diagnostics,
                    diagnostic_kind="integration_mypy",
                )

        # Gate 3: integration pytest
        # BC-177: hermetic invocation — PYTHONPATH is set explicitly (not
        #   inherited); --rootdir pins pytest's root to the workspace
        #   (prevents walking up to /tmp); -p no:cacheprovider avoids
        #   cross-run cache pollution.
        integration_tests = data.get("integration_tests")
        if integration_tests:
            test_path = tmp_path / "integration_tests.py"
            test_path.write_text(str(integration_tests))
            pytest_result = run_subprocess(
                cmd=[
                    exe,
                    "-m",
                    "pytest",
                    str(test_path),
                    "-x",
                    "--tb=short",
                    "-q",
                    f"--rootdir={tmp_path}",
                    "-p",
                    "no:cacheprovider",
                ],
                cwd=tmp_path,
                env=gate_subprocess_env(PYTHONPATH=str(tmp_path)),
                timeout_s=t.pytest_timeout,
            )
            if pytest_result.timed_out:
                return GateResult(
                    passed=False,
                    gate_name=GATE_NAME_INTEGRATION_PYTEST,
                    diagnostics=[
                        f"integration pytest timed out after {t.pytest_timeout}s",
                        "timed_out: True",
                    ],
                    diagnostic_kind="integration_pytest",
                )
            if "No module named pytest" in pytest_result.stderr:
                return GateResult(
                    passed=False,
                    gate_name=GATE_NAME_INTEGRATION_PYTEST,
                    diagnostics=["pytest not installed"],
                    diagnostic_kind="tool_not_found",
                )
            if pytest_result.returncode != 0:
                lines = pytest_result.stdout.strip().splitlines()
                err_lines = pytest_result.stderr.strip().splitlines()
                diagnostics = (lines + err_lines)[:10] or ["integration pytest reported failures"]
                return GateResult(
                    passed=False,
                    gate_name=GATE_NAME_INTEGRATION_PYTEST,
                    diagnostics=diagnostics,
                    diagnostic_kind="integration_pytest",
                )

    return GateResult(
        passed=True,
        gate_name=GATE_NAME_INTEGRATION,
        diagnostics=[],
    )
