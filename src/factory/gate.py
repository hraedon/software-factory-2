from __future__ import annotations

import ast
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class GateResult:
    passed: bool
    gate_name: str
    diagnostics: list[str] = field(default_factory=list)
    artifact_valid: bool = True
    diagnostic_kind: str = ""


def evaluate_interface_spec(artifact_path: Path, ac_ids: list[str] | None = None) -> GateResult:
    if not artifact_path.exists():
        return GateResult(
            passed=False,
            gate_name="interface_spec_file_exists",
            diagnostics=[f"Artifact not found: {artifact_path}"],
            artifact_valid=False,
            diagnostic_kind="file_exists",
        )
    content = artifact_path.read_text()
    if not content.strip():
        return GateResult(
            passed=False,
            gate_name="interface_spec_not_empty",
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
        gate_name="interface_spec",
        diagnostics=[],
        artifact_valid=True,
    )


def _check_syntax(content: str) -> GateResult:
    try:
        ast.parse(content)
    except SyntaxError as e:
        return GateResult(
            passed=False,
            gate_name="interface_spec_syntax",
            diagnostics=[f"SyntaxError at line {e.lineno}: {e.msg}"],
            artifact_valid=False,
            diagnostic_kind="syntax",
        )
    return GateResult(passed=True, gate_name="interface_spec_syntax")


def _check_pyi_stub(content: str, artifact_path: Path) -> GateResult:
    try:
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
                        gate_name="interface_spec_stub",
                        diagnostics=[
                            f"Function '{node.name}' has implementation body. "
                            f"Interface specs must use '...' as body."
                        ],
                        diagnostic_kind="stub",
                    )
    except SyntaxError:
        pass
    return GateResult(passed=True, gate_name="interface_spec_stub")



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
            gate_name="interface_spec_structural_semantics",
            diagnostics=["No top-level functions or classes defined — interface is vacuous"],
            diagnostic_kind="structural_semantics",
        )
    for node in top_level_defs:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.returns is None:
                return GateResult(
                    passed=False,
                    gate_name="interface_spec_structural_semantics",
                    diagnostics=[
                        f"Function '{node.name}' has no return type annotation — ambiguous contract"
                    ],
                    diagnostic_kind="structural_semantics",
                )
            non_self_params = [
                a
                for a in node.args.args + node.args.posonlyargs
                if a.arg != "self"
            ]
            if not non_self_params and not node.args.vararg and not node.args.kwarg:
                doc = ast.get_docstring(node, clean=False) or ""
                if not _has_ac_ref(doc):
                    return GateResult(
                        passed=False,
                        gate_name="interface_spec_structural_semantics",
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
                gate_name="interface_spec_structural_semantics",
                diagnostics=[
                    f"AC '{ac}' not in any function/class docstring — detached from contract"
                    for ac in unbound
                ],
                diagnostic_kind="structural_semantics",
            )
    return GateResult(passed=True, gate_name="interface_spec_structural_semantics")


def _has_ac_ref(text: str) -> bool:
    for word in text.replace(",", " ").split():
        if word.startswith("AC-") or word.startswith("TS-"):
            return True
    return False


def evaluate_test_suite(
    artifact_path: Path,
    interface_ref_pyi_path: Path | None = None,
) -> GateResult:
    if not artifact_path.exists():
        return GateResult(
            passed=False,
            gate_name="test_suite_file_exists",
            diagnostics=[f"Artifact not found: {artifact_path}"],
            artifact_valid=False,
            diagnostic_kind="file_exists",
        )

    content = artifact_path.read_text()
    if not content.strip():
        return GateResult(
            passed=False,
            gate_name="test_suite_not_empty",
            diagnostics=["Artifact is empty"],
            artifact_valid=False,
            diagnostic_kind="not_empty",
        )

    syntax_result = _check_syntax(content)
    if not syntax_result.passed:
        return GateResult(
            passed=syntax_result.passed,
            gate_name="test_suite_syntax",
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
                            gate_name="test_suite_import_forbidden",
                            diagnostics=[
                                f"Test imports forbidden module '{mod}' — must only reference "
                                f"the locked interface"
                            ],
                            artifact_valid=False,
                            diagnostic_kind="test_import_forbidden",
                        )
        except SyntaxError:
            pass

    return GateResult(
        passed=True,
        gate_name="test_suite",
        diagnostics=[],
        artifact_valid=True,
    )


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
) -> GateResult:
    if not artifact_path.exists():
        return GateResult(
            passed=False,
            gate_name="implementation_file_exists",
            diagnostics=[f"Artifact not found: {artifact_path}"],
            artifact_valid=False,
            diagnostic_kind="file_exists",
        )

    content = artifact_path.read_text()
    if not content.strip():
        return GateResult(
            passed=False,
            gate_name="implementation_not_empty",
            diagnostics=["Artifact is empty"],
            artifact_valid=False,
            diagnostic_kind="not_empty",
        )

    syntax_result = _check_syntax(content)
    if not syntax_result.passed:
        return GateResult(
            passed=syntax_result.passed,
            gate_name="implementation_syntax",
            diagnostics=syntax_result.diagnostics,
            artifact_valid=False,
            diagnostic_kind="syntax",
        )

    if interface_pyi_path is not None:
        import_result = _check_impl_imports(content)
        if not import_result.passed:
            return import_result

    if interface_pyi_path is not None:
        mypy_result = _run_mypy(artifact_path, interface_pyi_path)
        if not mypy_result.passed:
            return mypy_result

    if test_suite_path is not None:
        pytest_result = _run_pytest(artifact_path, test_suite_path)
        if not pytest_result.passed:
            return pytest_result

    ruff_result = _run_ruff(artifact_path)
    if not ruff_result.passed:
        return ruff_result

    return GateResult(
        passed=True,
        gate_name="implementation",
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
                        gate_name="implementation_import_forbidden",
                        diagnostics=[
                            f"Implementation imports forbidden module '{mod}'"
                        ],
                        artifact_valid=False,
                        diagnostic_kind="impl_import",
                    )
    except SyntaxError:
        pass
    return GateResult(passed=True, gate_name="implementation_imports")


def _is_forbidden_impl_import(module: str) -> bool:
    return module in ("conftest", "pytest")


def _run_mypy(artifact_path: Path, interface_pyi_path: Path) -> GateResult:
    mypy = shutil.which("mypy")
    if mypy is None:
        return GateResult(passed=True, gate_name="implementation_mypy")
    try:
        result = subprocess.run(
            [mypy, "--strict", "--no-error-summary", str(artifact_path)],
            capture_output=True,
            text=True,
            timeout=60,
            cwd=artifact_path.parent,
            env={**__import__("os").environ, "MYPYPATH": str(interface_pyi_path.parent)},
        )
        if result.returncode != 0:
            lines = result.stdout.strip().splitlines()
            diagnostics = lines[:10] if lines else ["mypy reported errors"]
            return GateResult(
                passed=False,
                gate_name="implementation_mypy",
                diagnostics=diagnostics,
                diagnostic_kind="impl_mypy",
            )
    except subprocess.TimeoutExpired:
        return GateResult(
            passed=False,
            gate_name="implementation_mypy",
            diagnostics=["mypy timed out after 60s"],
            diagnostic_kind="impl_mypy",
        )
    except Exception as e:
        return GateResult(
            passed=False,
            gate_name="implementation_mypy",
            diagnostics=[f"mypy invocation failed: {e}"],
            diagnostic_kind="impl_mypy",
        )
    return GateResult(passed=True, gate_name="implementation_mypy")


def _run_pytest(artifact_path: Path, test_suite_path: Path) -> GateResult:
    pytest_bin = shutil.which("pytest")
    if pytest_bin is None:
        return GateResult(passed=True, gate_name="implementation_pytest")
    try:
        result = subprocess.run(
            [
                pytest_bin,
                str(test_suite_path),
                "-x",
                "--tb=short",
                "-q",
            ],
            capture_output=True,
            text=True,
            timeout=120,
            cwd=artifact_path.parent,
            env={
                **__import__("os").environ,
                "PYTHONPATH": str(artifact_path.parent),
            },
        )
        if result.returncode != 0:
            lines = result.stdout.strip().splitlines()
            err_lines = result.stderr.strip().splitlines()
            diagnostics = (lines + err_lines)[:10] or ["pytest reported failures"]
            return GateResult(
                passed=False,
                gate_name="implementation_pytest",
                diagnostics=diagnostics,
                diagnostic_kind="impl_pytest",
            )
    except subprocess.TimeoutExpired:
        return GateResult(
            passed=False,
            gate_name="implementation_pytest",
            diagnostics=["pytest timed out after 120s"],
            diagnostic_kind="impl_pytest",
        )
    except Exception as e:
        return GateResult(
            passed=False,
            gate_name="implementation_pytest",
            diagnostics=[f"pytest invocation failed: {e}"],
            diagnostic_kind="impl_pytest",
        )
    return GateResult(passed=True, gate_name="implementation_pytest")


def _run_ruff(artifact_path: Path) -> GateResult:
    ruff = shutil.which("ruff")
    if ruff is None:
        return GateResult(passed=True, gate_name="implementation_lint")
    try:
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
                gate_name="implementation_lint",
                diagnostics=diagnostics,
                diagnostic_kind="impl_lint",
            )
    except subprocess.TimeoutExpired:
        return GateResult(
            passed=False,
            gate_name="implementation_lint",
            diagnostics=["ruff timed out after 30s"],
            diagnostic_kind="impl_lint",
        )
    except Exception as e:
        return GateResult(
            passed=False,
            gate_name="implementation_lint",
            diagnostics=[f"ruff invocation failed: {e}"],
            diagnostic_kind="impl_lint",
        )
    return GateResult(passed=True, gate_name="implementation_lint")


def evaluate_deterministic_gates(
    artifact_files: dict[str, Path],
    config: dict,
) -> list[GateResult]:
    results: list[GateResult] = []

    for artifact_key, artifact_path in artifact_files.items():
        if not artifact_path.exists():
            results.append(
                GateResult(
                    passed=False,
                    gate_name=f"{artifact_key}_file_exists",
                    diagnostics=[f"Artifact not found: {artifact_path}"],
                    artifact_valid=False,
                    diagnostic_kind="file_exists",
                )
            )
            continue

        content = artifact_path.read_text()
        if not content.strip():
            results.append(
                GateResult(
                    passed=False,
                    gate_name=f"{artifact_key}_not_empty",
                    diagnostics=[f"Artifact is empty: {artifact_path}"],
                    artifact_valid=False,
                    diagnostic_kind="not_empty",
                )
            )
            continue

        try:
            ast.parse(content)
        except SyntaxError as e:
            results.append(
                GateResult(
                    passed=False,
                    gate_name=f"{artifact_key}_syntax",
                    diagnostics=[f"SyntaxError at line {e.lineno}: {e.msg}"],
                    artifact_valid=False,
                    diagnostic_kind="syntax",
                )
            )
            continue

    return results


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
