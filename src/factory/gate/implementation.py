from __future__ import annotations

import ast
from pathlib import Path

from factory.config import GateTimeouts
from factory.constants import (
    GATE_NAME_IMPLEMENTATION,
    GATE_NAME_IMPLEMENTATION_FILE_EXISTS,
    GATE_NAME_IMPLEMENTATION_IMPORT_FORBIDDEN,
    GATE_NAME_IMPLEMENTATION_IMPORTS,
    GATE_NAME_IMPLEMENTATION_NOT_EMPTY,
    GATE_NAME_IMPLEMENTATION_SYNTAX,
    DiagnosticKind,
)
from factory.gate._base import GateResult, _guard_artifact_size
from factory.gate._subprocess import _run_mypy, _run_pytest, _run_ruff
from factory.gate.interface_spec import _check_syntax
from factory.gate.test_suite import _import_module_name

# tier: enforce
# precondition: interface_spec + test_suite gates are enforce; this gate runs after both
# audit trigger: re-evaluate if implementation gate is split into sub-gates


def evaluate_implementation(
    artifact_path: Path,
    test_suite_path: Path | None = None,
    interface_pyi_path: Path | None = None,
    dependency_pyi_paths: list[tuple[str, Path]] | None = None,
    dependency_spec_paths: list[tuple[str, Path]] | None = None,
    python_executable: str | None = None,
    gate_timeouts: GateTimeouts | None = None,
    mutation_enabled: bool = False,
    mutation_sample_size: int = 3,
    mutation_fail_threshold: float = 0.5,
    mutation_seed: int | None = None,
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
            diagnostic_kind=DiagnosticKind.FILE_EXISTS,
        )

    content = artifact_path.read_text()
    if not content.strip():
        return GateResult(
            passed=False,
            gate_name=GATE_NAME_IMPLEMENTATION_NOT_EMPTY,
            diagnostics=["Artifact is empty"],
            artifact_valid=False,
            diagnostic_kind=DiagnosticKind.NOT_EMPTY,
        )

    syntax_result = _check_syntax(content)
    if not syntax_result.passed:
        return GateResult(
            passed=syntax_result.passed,
            gate_name=GATE_NAME_IMPLEMENTATION_SYNTAX,
            diagnostics=syntax_result.diagnostics,
            artifact_valid=False,
            diagnostic_kind=DiagnosticKind.SYNTAX,
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

    if mutation_enabled and test_suite_path is not None:
        from factory.mutation_gate import evaluate_mutation_spot_check

        mutation_result = evaluate_mutation_spot_check(
            implementation_path=artifact_path,
            test_suite_path=test_suite_path,
            interface_pyi_path=interface_pyi_path,
            python_executable=python_executable,
            timeout=t.mutation_timeout,
            sample_size=mutation_sample_size,
            fail_threshold=mutation_fail_threshold,
            seed=mutation_seed,
        )
        if not mutation_result.passed:
            return mutation_result

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
            diagnostic_kind=DiagnosticKind.SYNTAX,
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
                    diagnostic_kind=DiagnosticKind.IMPL_IMPORT,
                )
    return GateResult(passed=True, gate_name=GATE_NAME_IMPLEMENTATION_IMPORTS)


def _is_forbidden_impl_import(module: str) -> bool:
    return module in ("conftest", "pytest")
