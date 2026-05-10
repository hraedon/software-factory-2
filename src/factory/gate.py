from __future__ import annotations

import ast
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from factory.constants import (
    ARTIFACT_FILENAME_INTERFACE,
    GATE_NAME_IMPLEMENTATION,
    GATE_NAME_IMPLEMENTATION_FILE_EXISTS,
    GATE_NAME_IMPLEMENTATION_IMPORT_FORBIDDEN,
    GATE_NAME_IMPLEMENTATION_IMPORTS,
    GATE_NAME_IMPLEMENTATION_LINT,
    GATE_NAME_IMPLEMENTATION_MYPY,
    GATE_NAME_IMPLEMENTATION_NOT_EMPTY,
    GATE_NAME_IMPLEMENTATION_PYTEST,
    GATE_NAME_IMPLEMENTATION_SYNTAX,
    GATE_NAME_INTERFACE_SPEC,
    GATE_NAME_INTERFACE_SPEC_FILE_EXISTS,
    GATE_NAME_INTERFACE_SPEC_NOT_EMPTY,
    GATE_NAME_INTERFACE_SPEC_STRUCTURAL_SEMANTICS,
    GATE_NAME_INTERFACE_SPEC_STUB,
    GATE_NAME_INTERFACE_SPEC_SYNTAX,
    GATE_NAME_TEST_SUITE,
    GATE_NAME_TEST_SUITE_ASSERTIONS,
    GATE_NAME_TEST_SUITE_COLLECT,
    GATE_NAME_TEST_SUITE_FILE_EXISTS,
    GATE_NAME_TEST_SUITE_IMPORT_FORBIDDEN,
    GATE_NAME_TEST_SUITE_NOT_EMPTY,
    GATE_NAME_TEST_SUITE_SYNTAX,
    TEMPFILE_PREFIX_COLLECT,
    TEMPFILE_PREFIX_MYPY,
    TEMPFILE_PREFIX_PYTEST,
)
from factory.pre_gate import copy_dependency_pyis


@dataclass(frozen=True)
class GateResult:
    passed: bool
    gate_name: str
    diagnostics: list[str] = field(default_factory=list)
    artifact_valid: bool = True
    diagnostic_kind: str = ""
    skipped: bool = False


def evaluate_interface_spec(artifact_path: Path, ac_ids: list[str] | None = None) -> GateResult:
    if not artifact_path.exists():
        return GateResult(
            passed=False,
            gate_name=GATE_NAME_INTERFACE_SPEC_FILE_EXISTS,
            diagnostics=[f"Artifact not found: {artifact_path}"],
            artifact_valid=False,
            diagnostic_kind="file_exists",
        )
    content = artifact_path.read_text()
    if not content.strip():
        return GateResult(
            passed=False,
            gate_name=GATE_NAME_INTERFACE_SPEC_NOT_EMPTY,
            diagnostics=["Artifact is empty"],
            artifact_valid=False,
            diagnostic_kind="not_empty",
        )
    syntax_result = _check_syntax(content)
    if not syntax_result.passed:
        return syntax_result
    stub_result = _check_pyi_stub(content, artifact_path)
    if not stub_result.passed:
        return stub_result
    structural_result = _check_structural_semantics(content, ac_ids)
    if not structural_result.passed:
        return structural_result
    return GateResult(
        passed=True,
        gate_name=GATE_NAME_INTERFACE_SPEC,
        diagnostics=[],
        artifact_valid=True,
    )


def _check_syntax(content: str) -> GateResult:
    try:
        ast.parse(content)
    except SyntaxError as e:
        return GateResult(
            passed=False,
            gate_name=GATE_NAME_INTERFACE_SPEC_SYNTAX,
            diagnostics=[f"SyntaxError at line {e.lineno}: {e.msg}"],
            artifact_valid=False,
            diagnostic_kind="syntax",
        )
    return GateResult(passed=True, gate_name=GATE_NAME_INTERFACE_SPEC_SYNTAX)


def _check_pyi_stub(content: str, artifact_path: Path) -> GateResult:
    tree = ast.parse(content)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            has_body = any(
                isinstance(stmt, (ast.Assign, ast.AugAssign, ast.Expr, ast.Return))
                for stmt in node.body
            )
            if has_body and not any(
                isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant)
                for stmt in node.body
            ):
                return GateResult(
                    passed=False,
                    gate_name=GATE_NAME_INTERFACE_SPEC_STUB,
                    diagnostics=[
                        f"Function '{node.name}' has implementation body. "
                        f"Interface specs must use '...' as body."
                    ],
                    diagnostic_kind="stub",
                )
    return GateResult(passed=True, gate_name=GATE_NAME_INTERFACE_SPEC_STUB)


def _check_structural_semantics(content: str, ac_ids: list[str] | None) -> GateResult:
    tree = ast.parse(content)
    top_level_defs = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]
    if not top_level_defs:
        return GateResult(
            passed=False,
            gate_name=GATE_NAME_INTERFACE_SPEC_STRUCTURAL_SEMANTICS,
            diagnostics=["No top-level functions or classes defined — interface is vacuous"],
            diagnostic_kind="structural_semantics",
        )
    for node in top_level_defs:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.returns is None:
                return GateResult(
                    passed=False,
                    gate_name=GATE_NAME_INTERFACE_SPEC_STRUCTURAL_SEMANTICS,
                    diagnostics=[
                        f"Function '{node.name}' has no return type annotation — ambiguous contract"
                    ],
                    diagnostic_kind="structural_semantics",
                )
            non_self_params = [a for a in node.args.args + node.args.posonlyargs if a.arg != "self"]
            if not non_self_params and not node.args.vararg and not node.args.kwarg:
                doc = ast.get_docstring(node, clean=False) or ""
                if not _has_ac_ref(doc):
                    return GateResult(
                        passed=False,
                        gate_name=GATE_NAME_INTERFACE_SPEC_STRUCTURAL_SEMANTICS,
                        diagnostics=[
                            f"Function '{node.name}' has no parameters and no AC reference in "
                            f"docstring — likely vacuous"
                        ],
                        diagnostic_kind="structural_semantics",
                    )
    if ac_ids:
        ac_to_node = {}
        mod_doc = ast.get_docstring(tree, clean=False) or ""
        for word in mod_doc.replace(",", " ").split():
            ref = word.rstrip(".")
            if ref.startswith("AC-") or ref.startswith("TS-"):
                ac_to_node.setdefault(ref, []).append("<module>")
        for node in top_level_defs:
            doc = ast.get_docstring(node, clean=False) or ""
            name = node.name
            for word in doc.replace(",", " ").split():
                ref = word.rstrip(".")
                if ref.startswith("AC-") or ref.startswith("TS-"):
                    ac_to_node.setdefault(ref, []).append(name)
        unbound = [ac for ac in ac_ids if ac not in ac_to_node]
        if unbound:
            return GateResult(
                passed=False,
                gate_name=GATE_NAME_INTERFACE_SPEC_STRUCTURAL_SEMANTICS,
                diagnostics=[
                    f"AC '{ac}' not in any function/class docstring — detached from contract"
                    for ac in unbound
                ],
                diagnostic_kind="structural_semantics",
            )
    return GateResult(passed=True, gate_name=GATE_NAME_INTERFACE_SPEC_STRUCTURAL_SEMANTICS)


def _has_ac_ref(text: str) -> bool:
    for word in text.replace(",", " ").split():
        if word.startswith("AC-") or word.startswith("TS-"):
            return True
    return False


def evaluate_test_suite(
    artifact_path: Path,
    interface_ref_pyi_path: Path | None = None,
    dependency_pyi_paths: list[tuple[str, Path]] | None = None,
    dependency_spec_paths: list[tuple[str, Path]] | None = None,
    python_executable: str | None = None,
) -> GateResult:
    if not artifact_path.exists():
        return GateResult(
            passed=False,
            gate_name=GATE_NAME_TEST_SUITE_FILE_EXISTS,
            diagnostics=[f"Artifact not found: {artifact_path}"],
            artifact_valid=False,
            diagnostic_kind="file_exists",
        )

    content = artifact_path.read_text()
    if not content.strip():
        return GateResult(
            passed=False,
            gate_name=GATE_NAME_TEST_SUITE_NOT_EMPTY,
            diagnostics=["Artifact is empty"],
            artifact_valid=False,
            diagnostic_kind="not_empty",
        )

    syntax_result = _check_syntax(content)
    if not syntax_result.passed:
        return GateResult(
            passed=syntax_result.passed,
            gate_name=GATE_NAME_TEST_SUITE_SYNTAX,
            diagnostics=syntax_result.diagnostics,
            artifact_valid=False,
            diagnostic_kind="syntax",
        )

    if interface_ref_pyi_path is not None:
        try:
            tree = ast.parse(content)
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    mod = _import_module_name(node)
                    if _is_non_interface_module(mod):
                        return GateResult(
                            passed=False,
                            gate_name=GATE_NAME_TEST_SUITE_IMPORT_FORBIDDEN,
                            diagnostics=[
                                f"Test imports forbidden module '{mod}' — must only reference "
                                f"the locked interface"
                            ],
                            artifact_valid=False,
                            diagnostic_kind="test_import_forbidden",
                        )
        except SyntaxError:
            pass

    collect_result = _run_pytest_collect(
        artifact_path,
        interface_ref_pyi_path,
        dependency_pyi_paths=dependency_pyi_paths,
        dependency_spec_paths=dependency_spec_paths,
        python_executable=python_executable,
    )
    if not collect_result.passed:
        return collect_result

    assertion_result = _check_assertion_count(artifact_path)
    if not assertion_result.passed:
        return assertion_result

    return GateResult(
        passed=True,
        gate_name=GATE_NAME_TEST_SUITE,
        diagnostics=[],
        artifact_valid=True,
    )


def _check_assertion_count(artifact_path: Path) -> GateResult:
    try:
        tree = ast.parse(artifact_path.read_text())
    except SyntaxError:
        return GateResult(passed=True, gate_name=GATE_NAME_TEST_SUITE_ASSERTIONS)

    test_functions: list[ast.FunctionDef | ast.AsyncFunctionDef] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name.startswith("test_"):
                test_functions.append(node)

    if not test_functions:
        return GateResult(passed=True, gate_name=GATE_NAME_TEST_SUITE_ASSERTIONS)

    total_assertions = 0
    zero_assert_funcs: list[str] = []
    for func in test_functions:
        count = _count_asserts(func)
        total_assertions += count
        if count == 0:
            zero_assert_funcs.append(func.name)

    if zero_assert_funcs:
        return GateResult(
            passed=False,
            gate_name=GATE_NAME_TEST_SUITE_ASSERTIONS,
            diagnostics=[f"Test function(s) with zero assertions: {', '.join(zero_assert_funcs)}"],
            diagnostic_kind="test_no_assertions",
        )

    if total_assertions < len(test_functions):
        return GateResult(
            passed=False,
            gate_name=GATE_NAME_TEST_SUITE_ASSERTIONS,
            diagnostics=[
                f"Total assertions ({total_assertions}) < test functions ({len(test_functions)})"
            ],
            diagnostic_kind="test_no_assertions",
        )

    return GateResult(passed=True, gate_name=GATE_NAME_TEST_SUITE_ASSERTIONS)


def _count_asserts(node: ast.AST) -> int:
    count = 0
    for child in ast.walk(node):
        if isinstance(child, ast.Assert):
            count += 1
    return count


def _import_module_name(node: ast.Import | ast.ImportFrom) -> str:
    if isinstance(node, ast.Import):
        return node.names[0].name.split(".")[0]
    module = node.module or ""
    return module.split(".")[0]


def _is_non_interface_module(module: str) -> bool:
    return module in ("_impl", "implementation", "src")


def evaluate_implementation(
    artifact_path: Path,
    test_suite_path: Path | None = None,
    interface_pyi_path: Path | None = None,
    dependency_pyi_paths: list[tuple[str, Path]] | None = None,
    dependency_spec_paths: list[tuple[str, Path]] | None = None,
    python_executable: str | None = None,
) -> GateResult:
    if not artifact_path.exists():
        return GateResult(
            passed=False,
            gate_name=GATE_NAME_IMPLEMENTATION_FILE_EXISTS,
            diagnostics=[f"Artifact not found: {artifact_path}"],
            artifact_valid=False,
            diagnostic_kind="file_exists",
        )

    content = artifact_path.read_text()
    if not content.strip():
        return GateResult(
            passed=False,
            gate_name=GATE_NAME_IMPLEMENTATION_NOT_EMPTY,
            diagnostics=["Artifact is empty"],
            artifact_valid=False,
            diagnostic_kind="not_empty",
        )

    syntax_result = _check_syntax(content)
    if not syntax_result.passed:
        return GateResult(
            passed=syntax_result.passed,
            gate_name=GATE_NAME_IMPLEMENTATION_SYNTAX,
            diagnostics=syntax_result.diagnostics,
            artifact_valid=False,
            diagnostic_kind="syntax",
        )

    if interface_pyi_path is not None:
        import_result = _check_impl_imports(content)
        if not import_result.passed:
            return import_result

    if interface_pyi_path is not None:
        mypy_result = _run_mypy(
            artifact_path,
            interface_pyi_path,
            dependency_pyi_paths=dependency_pyi_paths,
            dependency_spec_paths=dependency_spec_paths,
            python_executable=python_executable,
        )
        if not mypy_result.passed:
            return mypy_result

    if test_suite_path is not None:
        pytest_result = _run_pytest(
            artifact_path,
            test_suite_path,
            dependency_pyi_paths=dependency_pyi_paths,
            dependency_spec_paths=dependency_spec_paths,
            python_executable=python_executable,
        )
        if not pytest_result.passed:
            return pytest_result

    ruff_result = _run_ruff(artifact_path, python_executable=python_executable)
    if not ruff_result.passed:
        return ruff_result

    return GateResult(
        passed=True,
        gate_name=GATE_NAME_IMPLEMENTATION,
        diagnostics=[],
        artifact_valid=True,
    )


def _check_impl_imports(content: str) -> GateResult:
    try:
        tree = ast.parse(content)
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                mod = _import_module_name(node)
                if _is_forbidden_impl_import(mod):
                    return GateResult(
                        passed=False,
                        gate_name=GATE_NAME_IMPLEMENTATION_IMPORT_FORBIDDEN,
                        diagnostics=[f"Implementation imports forbidden module '{mod}'"],
                        artifact_valid=False,
                        diagnostic_kind="impl_import",
                    )
    except SyntaxError:
        pass
    return GateResult(passed=True, gate_name=GATE_NAME_IMPLEMENTATION_IMPORTS)


def _is_forbidden_impl_import(module: str) -> bool:
    return module in ("conftest", "pytest")


def _run_pytest_collect(
    artifact_path: Path,
    interface_ref_pyi_path: Path | None = None,
    dependency_pyi_paths: list[tuple[str, Path]] | None = None,
    dependency_spec_paths: list[tuple[str, Path]] | None = None,
    python_executable: str | None = None,
) -> GateResult:
    import os
    import tempfile

    exe = python_executable or sys.executable
    try:
        with tempfile.TemporaryDirectory(prefix=TEMPFILE_PREFIX_COLLECT) as tmpdir:
            test_copy = Path(tmpdir) / artifact_path.name
            test_copy.write_text(artifact_path.read_text())
            if interface_ref_pyi_path is not None and interface_ref_pyi_path.exists():
                iface_copy = Path(tmpdir) / "interface.py"
                iface_copy.write_text(interface_ref_pyi_path.read_text())
            copy_dependency_pyis(tmpdir, dependency_pyi_paths, dependency_spec_paths)
            result = subprocess.run(
                [exe, "-m", "pytest", "--collect-only", "-q", str(test_copy)],
                capture_output=True,
                text=True,
                timeout=30,
                cwd=tmpdir,
                env={
                    **os.environ,
                    "PYTHONPATH": tmpdir,
                },
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
    except subprocess.TimeoutExpired:
        return GateResult(
            passed=False,
            gate_name=GATE_NAME_TEST_SUITE_COLLECT,
            diagnostics=["pytest --collect-only timed out after 30s"],
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
) -> GateResult:
    import os
    import tempfile

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
    except subprocess.TimeoutExpired:
        return GateResult(
            passed=False,
            gate_name=GATE_NAME_IMPLEMENTATION_MYPY,
            diagnostics=["mypy timed out after 60s"],
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
) -> GateResult:
    import os
    import tempfile

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
    except subprocess.TimeoutExpired:
        return GateResult(
            passed=False,
            gate_name=GATE_NAME_IMPLEMENTATION_PYTEST,
            diagnostics=["pytest timed out after 120s"],
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
        subprocess.run(
            [ruff, "check", "--fix", str(artifact_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        subprocess.run(
            [ruff, "format", str(artifact_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        result = subprocess.run(
            [ruff, "check", str(artifact_path)],
            capture_output=True,
            text=True,
            timeout=30,
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
    except subprocess.TimeoutExpired:
        return GateResult(
            passed=False,
            gate_name=GATE_NAME_IMPLEMENTATION_LINT,
            diagnostics=["ruff timed out after 30s"],
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


def structural_signature(pyi_content: str) -> list[str]:
    """Extract normalized structural elements from .pyi content for comparison.

    Returns a sorted list of canonical strings capturing:
    - function names, parameter types, and return types
    - class names
    - enum member names and values
    - type aliases (module-level assignments with annotations)
    - AC references from docstrings

    Whitespace, import ordering, and prose docstring content are excluded.
    """
    tree = ast.parse(pyi_content)
    elements: set[str] = set()

    def _type_str(node: ast.expr | None) -> str:
        if node is None:
            return ""
        return ast.unparse(node)

    def _extract_ac_refs(node) -> list[str]:
        doc = ast.get_docstring(node, clean=False)
        if not doc:
            return []
        refs: list[str] = []
        for word in doc.replace(",", " ").split():
            if word.startswith("AC-") or word.startswith("TS-"):
                refs.append(word.rstrip("."))
        return refs

    def _visit_module_level(stmts: list[ast.stmt]):
        for node in stmts:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                _collect_function(node)
            elif isinstance(node, ast.ClassDef):
                _collect_class(node)
            elif isinstance(node, ast.AnnAssign):
                target = node.target
                if isinstance(target, ast.Name):
                    elements.add(f"type_alias:{target.id}={_type_str(node.annotation)}")
            elif isinstance(node, ast.Assign) and len(node.targets) == 1:
                target = node.targets[0]
                if isinstance(target, ast.Name) and isinstance(node.value, ast.Subscript):
                    elements.add(f"type_alias:{target.id}={ast.unparse(node.value)}")

    def _collect_function(node: ast.FunctionDef | ast.AsyncFunctionDef):
        params = []
        for arg in node.args.args + node.args.posonlyargs:
            params.append(f"{arg.arg}:{_type_str(arg.annotation)}")
        if node.args.vararg:
            params.append(f"*{node.args.vararg.arg}:{_type_str(node.args.vararg.annotation)}")
        if node.args.kwonlyargs:
            for kwa in node.args.kwonlyargs:
                params.append(f"{kwa.arg}:{_type_str(kwa.annotation)}")
        if node.args.kwarg:
            params.append(f"**{node.args.kwarg.arg}:{_type_str(node.args.kwarg.annotation)}")
        ret = _type_str(node.returns)
        elements.add(f"fn:{node.name}({', '.join(params)}) -> {ret}")
        for ref in _extract_ac_refs(node):
            elements.add(f"ac_ref:{node.name}:{ref}")

    def _collect_class(node: ast.ClassDef):
        elements.add(f"class:{node.name}")
        for ref in _extract_ac_refs(node):
            elements.add(f"ac_ref:{node.name}:{ref}")
        for body_node in node.body:
            if isinstance(body_node, ast.Assign):
                for target in body_node.targets:
                    if isinstance(target, ast.Name):
                        val = ast.unparse(body_node.value) if body_node.value else ""
                        elements.add(f"enum_member:{node.name}.{target.id}={val}")

    _visit_module_level(tree.body)
    return sorted(elements)


def structurally_equivalent_pyi(a: str, b: str) -> bool:
    """Return True if two .pyi contents are structurally equivalent.

    Compares function signatures, class names, enum members, type aliases, and AC
    references. Ignores formatting, whitespace, import ordering, and docstring prose.
    """
    try:
        sig_a = structural_signature(a)
        sig_b = structural_signature(b)
        return sig_a == sig_b
    except SyntaxError:
        return False
