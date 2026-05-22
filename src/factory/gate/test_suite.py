from __future__ import annotations

import ast
from pathlib import Path

from factory.config import GateTimeouts
from factory.constants import (
    GATE_NAME_TEST_SUITE,
    GATE_NAME_TEST_SUITE_ASSERTIONS,
    GATE_NAME_TEST_SUITE_FILE_EXISTS,
    GATE_NAME_TEST_SUITE_IMPORT_FORBIDDEN,
    GATE_NAME_TEST_SUITE_NOT_EMPTY,
    GATE_NAME_TEST_SUITE_SYNTAX,
)
from factory.gate._base import GateResult, _guard_artifact_size
from factory.gate._subprocess import _run_pytest_collect
from factory.gate.interface_spec import _check_syntax


# tier: enforce
# precondition: interface_spec gate has passed; test_suite validates against locked interface
# audit trigger: re-evaluate if test collection/assertion rules change
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
