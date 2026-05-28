from __future__ import annotations

import ast
from pathlib import Path

from factory.constants import (
    GATE_NAME_INTERFACE_SPEC,
    GATE_NAME_INTERFACE_SPEC_FILE_EXISTS,
    GATE_NAME_INTERFACE_SPEC_NOT_EMPTY,
    GATE_NAME_INTERFACE_SPEC_STRUCTURAL_SEMANTICS,
    GATE_NAME_INTERFACE_SPEC_STUB,
    GATE_NAME_INTERFACE_SPEC_SYNTAX,
    DiagnosticKind,
)
from factory.gate._base import GateResult, _guard_artifact_size


# tier: enforce
# precondition: first gate in the pipeline; all downstream gates depend on this passing
# audit trigger: re-evaluate if interface_spec format changes or becomes optional
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
            diagnostic_kind=DiagnosticKind.FILE_EXISTS,
        )
    content = artifact_path.read_text()
    if not content.strip():
        return GateResult(
            passed=False,
            gate_name=GATE_NAME_INTERFACE_SPEC_NOT_EMPTY,
            diagnostics=["Artifact is empty"],
            artifact_valid=False,
            diagnostic_kind=DiagnosticKind.NOT_EMPTY,
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
            diagnostic_kind=DiagnosticKind.SYNTAX,
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
                    diagnostic_kind=DiagnosticKind.STUB,
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
            diagnostic_kind=DiagnosticKind.STRUCTURAL_SEMANTICS,
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
                    diagnostic_kind=DiagnosticKind.STRUCTURAL_SEMANTICS,
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
                        diagnostic_kind=DiagnosticKind.STRUCTURAL_SEMANTICS,
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
                diagnostic_kind=DiagnosticKind.STRUCTURAL_SEMANTICS,
            )
    return GateResult(passed=True, gate_name=GATE_NAME_INTERFACE_SPEC_STRUCTURAL_SEMANTICS)


def _has_ac_ref(text: str) -> bool:
    for word in text.replace(",", " ").split():
        if word.startswith("AC-") or word.startswith("TS-"):
            return True
    return False
