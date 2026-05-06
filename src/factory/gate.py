from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class GateResult:
    passed: bool
    gate_name: str
    diagnostics: list[str] = field(default_factory=list)
    artifact_valid: bool = True


def evaluate_interface_spec(artifact_path: Path, ac_ids: list[str] | None = None) -> GateResult:
    if not artifact_path.exists():
        return GateResult(
            passed=False,
            gate_name="interface_spec_file_exists",
            diagnostics=[f"Artifact not found: {artifact_path}"],
            artifact_valid=False,
        )
    content = artifact_path.read_text()
    if not content.strip():
        return GateResult(
            passed=False,
            gate_name="interface_spec_not_empty",
            diagnostics=["Artifact is empty"],
            artifact_valid=False,
        )
    syntax_result = _check_syntax(content)
    if not syntax_result.passed:
        return syntax_result
    stub_result = _check_pyi_stub(content, artifact_path)
    if not stub_result.passed:
        return stub_result
    if ac_ids is not None:
        ac_result = _check_ac_references(content, ac_ids)
        if not ac_result.passed:
            return ac_result
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
        )
    return GateResult(passed=True, gate_name="interface_spec_syntax")


def _check_pyi_stub(content: str, artifact_path: Path) -> GateResult:
    if artifact_path.suffix == ".pyi":
        pass
    else:
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
                        )
        except SyntaxError:
            pass
    return GateResult(passed=True, gate_name="interface_spec_stub")


def _check_ac_references(content: str, ac_ids: list[str]) -> GateResult:
    missing = []
    for ac_id in ac_ids:
        if ac_id not in content:
            missing.append(ac_id)
    if missing:
        return GateResult(
            passed=False,
            gate_name="interface_spec_ac_references",
            diagnostics=[
                f"AC reference missing: {ac_id}" for ac_id in missing
            ],
        )
    return GateResult(passed=True, gate_name="interface_spec_ac_references")
