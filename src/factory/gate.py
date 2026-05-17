from __future__ import annotations

import ast
import shutil
import subprocess
import sys
import warnings
from dataclasses import dataclass, field
from pathlib import Path

from factory.config import GateTimeouts
from factory.constants import (
    ARTIFACT_FILENAME_INTERFACE,
    CUSTOM_FIELD_REVIEW_FINDINGS,
    GATE_NAME_CROSS_FAMILY_REVIEW,
    GATE_NAME_IMPLEMENTATION,
    GATE_NAME_IMPLEMENTATION_FILE_EXISTS,
    GATE_NAME_IMPLEMENTATION_IMPORT_FORBIDDEN,
    GATE_NAME_IMPLEMENTATION_IMPORTS,
    GATE_NAME_IMPLEMENTATION_LINT,
    GATE_NAME_IMPLEMENTATION_MYPY,
    GATE_NAME_IMPLEMENTATION_NOT_EMPTY,
    GATE_NAME_IMPLEMENTATION_PYTEST,
    GATE_NAME_IMPLEMENTATION_SYNTAX,
    GATE_NAME_INTEGRATION,
    GATE_NAME_INTEGRATION_IMPORT,
    GATE_NAME_INTEGRATION_MYPY,
    GATE_NAME_INTEGRATION_PYTEST,
    GATE_NAME_INTERFACE_SPEC,
    GATE_NAME_INTERFACE_SPEC_FILE_EXISTS,
    GATE_NAME_INTERFACE_SPEC_NOT_EMPTY,
    GATE_NAME_INTERFACE_SPEC_STRUCTURAL_SEMANTICS,
    GATE_NAME_INTERFACE_SPEC_STUB,
    GATE_NAME_INTERFACE_SPEC_SYNTAX,
    GATE_NAME_JURY_DISAGREE,
    GATE_NAME_JURY_QUORUM,
    GATE_NAME_OUTCOME_E2E,
    GATE_NAME_TEST_SUITE,
    GATE_NAME_TEST_SUITE_ASSERTIONS,
    GATE_NAME_TEST_SUITE_COLLECT,
    GATE_NAME_TEST_SUITE_FILE_EXISTS,
    GATE_NAME_TEST_SUITE_IMPORT_FORBIDDEN,
    GATE_NAME_TEST_SUITE_NOT_EMPTY,
    GATE_NAME_TEST_SUITE_SYNTAX,
    MAX_ARTIFACT_SIZE_BYTES,
    TEMPFILE_PREFIX_COLLECT,
    TEMPFILE_PREFIX_MYPY,
    TEMPFILE_PREFIX_PYTEST,
)
from factory.output_extraction import extract_json_from_output
from factory.pre_gate import copy_dependency_pyis
from factory.sandbox import gate_subprocess_env


@dataclass(frozen=True)
class GateResult:
    passed: bool
    gate_name: str
    diagnostics: list[str] = field(default_factory=list)
    artifact_valid: bool = True
    diagnostic_kind: str = ""
    skipped: bool = False
    transition_fields: dict = field(default_factory=dict)
    """Custom fields to merge into the current work item's transition payload."""
    routing_fields: dict = field(default_factory=dict)
    """Custom fields to propagate to an upstream revision created by the router."""
    routing_hint: dict | None = None
    # Deprecated: use transition_fields or routing_fields instead.
    # Kept for one migration cycle. Maps to transition_fields.
    custom_fields: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.custom_fields:
            warnings.warn(
                "GateResult.custom_fields is deprecated; use transition_fields or routing_fields",
                DeprecationWarning,
                stacklevel=2,
            )
            # Merge into transition_fields for backwards compatibility
            merged = {**self.custom_fields, **self.transition_fields}
            object.__setattr__(self, "transition_fields", merged)
            object.__setattr__(self, "custom_fields", {})


def _guard_artifact_size(artifact_path: Path) -> GateResult | None:
    try:
        size = artifact_path.stat().st_size
    except OSError:
        return None
    if size > MAX_ARTIFACT_SIZE_BYTES:
        return GateResult(
            passed=False,
            gate_name="artifact_oversized",
            diagnostics=[
                f"Artifact size {size} bytes exceeds gate limit {MAX_ARTIFACT_SIZE_BYTES} bytes"
            ],
            artifact_valid=False,
            diagnostic_kind="artifact_oversized",
        )
    return None


def evaluate_interface_spec(artifact_path: Path, ac_ids: list[str] | None = None) -> GateResult:
    size_guard = _guard_artifact_size(artifact_path)
    if size_guard is not None:
        return size_guard
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
            for stmt in node.body:
                if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
                    if stmt.value.value is ...:
                        continue
                    if isinstance(stmt.value.value, str):
                        continue  # docstring
                if isinstance(stmt, ast.Pass):
                    continue
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
            non_self_params = [
                a
                for a in node.args.args + node.args.posonlyargs + node.args.kwonlyargs
                if a.arg != "self"
            ]
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
    gate_timeouts: GateTimeouts | None = None,
) -> GateResult:
    size_guard = _guard_artifact_size(artifact_path)
    if size_guard is not None:
        return size_guard
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
        except SyntaxError as e:
            return GateResult(
                passed=False,
                gate_name=GATE_NAME_TEST_SUITE_IMPORT_FORBIDDEN,
                diagnostics=[f"SyntaxError at line {e.lineno}: {e.msg}"],
                artifact_valid=False,
                diagnostic_kind="syntax",
            )
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

    collect_result = _run_pytest_collect(
        artifact_path,
        interface_ref_pyi_path,
        dependency_pyi_paths=dependency_pyi_paths,
        dependency_spec_paths=dependency_spec_paths,
        python_executable=python_executable,
        timeout=gate_timeouts.collect_timeout if gate_timeouts else 30,
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
    except SyntaxError as e:
        return GateResult(
            passed=False,
            gate_name=GATE_NAME_TEST_SUITE_ASSERTIONS,
            diagnostics=[f"SyntaxError at line {e.lineno}: {e.msg}"],
            artifact_valid=False,
            diagnostic_kind="syntax",
        )

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


_PYTEST_ASSERT_NAMES = frozenset({"raises", "warns", "deprecated_call"})


def _call_name(call: ast.Call) -> str | None:
    func = call.func
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        return func.attr
    return None


def _count_asserts(node: ast.AST) -> int:
    count = 0
    with_context_calls: set[int] = set()
    for child in ast.walk(node):
        if isinstance(child, ast.With):
            for item in child.items:
                expr = item.context_expr
                if isinstance(expr, ast.Call):
                    with_context_calls.add(id(expr))
                    if _call_name(expr) in _PYTEST_ASSERT_NAMES:
                        count += 1
    for child in ast.walk(node):
        if isinstance(child, ast.Assert):
            count += 1
            continue
        if isinstance(child, ast.Call) and id(child) not in with_context_calls:
            name = _call_name(child)
            if name is None:
                continue
            if name in _PYTEST_ASSERT_NAMES and isinstance(child.func, ast.Attribute):
                count += 1
            elif isinstance(child.func, ast.Attribute) and child.func.attr.startswith("assert"):
                count += 1
    return count


def _import_module_name(node: ast.Import | ast.ImportFrom) -> str:
    if isinstance(node, ast.Import):
        return node.names[0].name.split(".")[0]
    module = node.module or ""
    if module:
        return module.split(".")[0]
    # Relative import without module: from . import name
    if node.names:
        return node.names[0].name.split(".")[0]
    return ""


def _is_non_interface_module(module: str) -> bool:
    return module in ("_impl", "implementation", "src")


def evaluate_implementation(
    artifact_path: Path,
    test_suite_path: Path | None = None,
    interface_pyi_path: Path | None = None,
    dependency_pyi_paths: list[tuple[str, Path]] | None = None,
    dependency_spec_paths: list[tuple[str, Path]] | None = None,
    python_executable: str | None = None,
    gate_timeouts: GateTimeouts | None = None,
) -> GateResult:
    t = gate_timeouts or GateTimeouts()
    size_guard = _guard_artifact_size(artifact_path)
    if size_guard is not None:
        return size_guard
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
            timeout=t.mypy_timeout,
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
            timeout=t.pytest_timeout,
        )
        if not pytest_result.passed:
            return pytest_result

    ruff_result = _run_ruff(
        artifact_path, python_executable=python_executable, timeout=t.ruff_timeout
    )
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
    except SyntaxError as e:
        return GateResult(
            passed=False,
            gate_name=GATE_NAME_IMPLEMENTATION_IMPORTS,
            diagnostics=[f"SyntaxError at line {e.lineno}: {e.msg}"],
            artifact_valid=False,
            diagnostic_kind="syntax",
        )
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
    return GateResult(passed=True, gate_name=GATE_NAME_IMPLEMENTATION_IMPORTS)


def _is_forbidden_impl_import(module: str) -> bool:
    return module in ("conftest", "pytest")


def _run_pytest_collect(
    artifact_path: Path,
    interface_ref_pyi_path: Path | None = None,
    dependency_pyi_paths: list[tuple[str, Path]] | None = None,
    dependency_spec_paths: list[tuple[str, Path]] | None = None,
    python_executable: str | None = None,
    timeout: int = 30,
) -> GateResult:
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
                timeout=timeout,
                cwd=tmpdir,
                env=gate_subprocess_env(PYTHONPATH=tmpdir),
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
            diagnostics=[f"pytest --collect-only timed out after {timeout}s"],
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
                [
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
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=tmpdir,
                env=gate_subprocess_env(MYPYPATH=tmpdir),
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
            diagnostics=[f"mypy timed out after {timeout}s"],
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
                timeout=timeout,
                cwd=tmpdir,
                env=gate_subprocess_env(PYTHONPATH=tmpdir),
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
            diagnostics=[f"pytest timed out after {timeout}s"],
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
    import tempfile

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
            subprocess.run(
                [ruff, "check", "--fix", str(tmp_copy)],
                capture_output=True,
                text=True,
                timeout=timeout,
                env=ruff_env,
            )
            subprocess.run(
                [ruff, "format", str(tmp_copy)],
                capture_output=True,
                text=True,
                timeout=timeout,
                env=ruff_env,
            )
            result = subprocess.run(
                [ruff, "check", str(tmp_copy)],
                capture_output=True,
                text=True,
                timeout=timeout,
                env=ruff_env,
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
            diagnostics=[f"ruff timed out after {timeout}s"],
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


def extract_exports(pyi_content: str) -> set[str]:
    """Extract top-level public names from .pyi content.

    Returns a flat set of exported names (classes, functions, type aliases).
    Enum members collapse to their parent class name.
    """
    tree = ast.parse(pyi_content)
    names: set[str] = set()

    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(node.name)
        elif isinstance(node, ast.ClassDef):
            names.add(node.name)
        elif isinstance(node, ast.AnnAssign):
            if isinstance(node.target, ast.Name):
                names.add(node.target.id)
        elif isinstance(node, ast.Assign) and len(node.targets) == 1:
            if isinstance(node.targets[0], ast.Name):
                names.add(node.targets[0].id)
    return names


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


# ---------------------------------------------------------------------------
# Phase 4: Review and Jury gates
# ---------------------------------------------------------------------------


def _extract_json_vote(path: Path) -> dict:
    """Read a JSON artifact and return the parsed vote object."""
    if not path.exists():
        return {}
    try:
        text = path.read_text()
    except Exception:
        return {}
    extracted = extract_json_from_output(text)
    if extracted is None:
        return {}
    if isinstance(extracted, dict):
        return extracted
    try:
        import json

        return json.loads(str(extracted))
    except json.JSONDecodeError:
        return {}


def evaluate_review(artifact_path: Path) -> GateResult:
    """Evaluate a cross-family review artifact.

    Expects a JSON object with `passed` (boolean), `findings` (list of dicts with
    ac_id/kind/severity/body), and `rationale` (string).

    Emits `diagnostic_kind`:
    - "review_malformed" — reviewer output was empty, unparseable, or missing required fields.
    - "review_found_defect" — reviewer produced a valid verdict that found substantive defects.
    """
    vote = _extract_json_vote(artifact_path)
    if not vote:
        return GateResult(
            passed=False,
            gate_name=GATE_NAME_CROSS_FAMILY_REVIEW,
            diagnostics=["Reviewer produced no parseable JSON output"],
            diagnostic_kind="review_malformed",
        )
    passed = bool(vote.get("passed"))
    raw_findings = vote.get("findings", [])
    if not isinstance(raw_findings, list):
        raw_findings = []
    rationale = str(vote.get("rationale", ""))
    diagnostics: list[str] = []
    structured_findings: list[dict] = []
    has_structured_findings = False
    if not passed:
        if raw_findings:
            for item in raw_findings:
                if isinstance(item, dict) and "body" in item:
                    has_structured_findings = True
                    structured_findings.append(item)
                    diagnostics.append(
                        f"[{item.get('severity', 'block')}] "
                        f"{item.get('ac_id', '')} "
                        f"({item.get('kind', 'impl')}): {item['body']}"
                    )
                else:
                    diagnostics.append(str(item))
        else:
            diagnostics.append("Review did not pass and provided no findings.")
        if rationale:
            diagnostics.append(f"Rationale: {rationale}")
    # Malformed: no parseable JSON at all, or valid JSON but missing required shape on failure
    malformed = not passed and not has_structured_findings and not rationale
    diagnostic_kind = ""
    if not passed:
        diagnostic_kind = "review_malformed" if malformed else "review_found_defect"
    routing_fields: dict = {}
    if structured_findings:
        routing_fields[CUSTOM_FIELD_REVIEW_FINDINGS] = structured_findings
    return GateResult(
        passed=passed,
        gate_name=GATE_NAME_CROSS_FAMILY_REVIEW,
        diagnostics=diagnostics,
        diagnostic_kind=diagnostic_kind,
        routing_fields=routing_fields,
    )


def evaluate_jury(artifact_path: Path) -> GateResult:
    """Evaluate a jury verdict artifact.

    Expects a JSON object with `quorum_met` (boolean), `votes_for`, `votes_against`,
    and optionally `disagreement_rationale`.
    """
    vote = _extract_json_vote(artifact_path)
    quorum_met = bool(vote.get("quorum_met"))
    passed = quorum_met
    votes_for = int(vote.get("votes_for", 0))
    votes_against = int(vote.get("votes_against", 0))
    disagreement = str(vote.get("disagreement_rationale", ""))
    diagnostics: list[str] = []
    if not passed:
        diagnostics.append(f"Jury quorum not met ({votes_for} for, {votes_against} against).")
        if disagreement.startswith("[all_against]"):
            diagnostics.append(f"All jurors against: {disagreement.removeprefix('[all_against] ')}")
        elif disagreement:
            diagnostics.append(f"Disagreement: {disagreement}")
    gate_name = GATE_NAME_JURY_QUORUM if passed else GATE_NAME_JURY_DISAGREE
    return GateResult(
        passed=passed,
        gate_name=gate_name,
        diagnostics=diagnostics,
        diagnostic_kind="jury" if not passed else "",
    )


# ---------------------------------------------------------------------------
# Phase 5: Integration and outcome-verification gates
# ---------------------------------------------------------------------------


def evaluate_integration(
    artifact_path: Path,
    python_executable: str | None = None,
    gate_timeouts: GateTimeouts | None = None,
) -> GateResult:
    """Evaluate an integration artifact.

    Expects a JSON object with `assembled_tree` (dict of filename -> source).
    Mechanical gates: import resolution, mypy, pytest on assembled tree.
    """
    import json
    import subprocess
    import tempfile

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
        tmp_path = Path(tmpdir)
        for filename, source in assembled_tree.items():
            dest = tmp_path / filename
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
        import_result = subprocess.run(
            [exe, "-c", _import_check_script, str(tmp_path)],
            capture_output=True,
            text=True,
            timeout=t.pytest_timeout,
            cwd=str(tmp_path),
            env=gate_subprocess_env(PYTHONPATH=str(tmp_path)),
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
            mypy_result = subprocess.run(
                [
                    exe,
                    "-m",
                    "mypy",
                    "--strict",
                    "--no-error-summary",
                    "--explicit-package-bases",
                    "--allow-empty-bodies",
                    str(tmp_path),
                ],
                capture_output=True,
                text=True,
                timeout=t.mypy_timeout,
                cwd=str(tmp_path),
                env=gate_subprocess_env(MYPYPATH=str(tmp_path)),
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
            pytest_result = subprocess.run(
                [
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
                capture_output=True,
                text=True,
                timeout=t.pytest_timeout,
                cwd=str(tmp_path),
                env=gate_subprocess_env(PYTHONPATH=str(tmp_path)),
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


def evaluate_outcome_verification(artifact_path: Path) -> GateResult:
    """Evaluate an outcome-verification artifact.

    Expects a JSON object with `verdict` ("pass"/"fail"/"cannot_proceed")
    and optionally `routing_hint`.
    """
    vote = _extract_json_vote(artifact_path)
    verdict = str(vote.get("verdict", "")).lower()
    passed = verdict == "pass"
    rationale = str(vote.get("rationale", ""))
    diagnostics: list[str] = []
    if verdict == "cannot_proceed":
        return GateResult(
            passed=False,
            gate_name=GATE_NAME_OUTCOME_E2E,
            diagnostics=[
                f"Outcome verifier returned cannot_proceed: {rationale or 'no rationale'}"
            ],
            diagnostic_kind="outcome_e2e",
        )
    routing_hint: dict | None = None
    if not passed:
        diagnostics.append(f"Outcome verification failed: {rationale or 'no rationale provided'}")
        vote_hint = vote.get("routing_hint")
        if isinstance(vote_hint, dict):
            hint_type = vote_hint.get("work_item_type", "unknown")
            hint_reason = vote_hint.get("reason", "")
            diagnostics.append(f"Routing hint: {hint_type} — {hint_reason}")
            routing_hint = vote_hint
    return GateResult(
        passed=passed,
        gate_name=GATE_NAME_OUTCOME_E2E,
        diagnostics=diagnostics,
        diagnostic_kind="outcome_e2e" if not passed else "",
        routing_hint=routing_hint,
    )
