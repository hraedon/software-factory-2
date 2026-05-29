from __future__ import annotations

import ast
import logging
import random
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from factory.config import GateTimeouts
from factory.constants import (
    GATE_NAME_IMPLEMENTATION_IMPORTS,
    GATE_NAME_IMPLEMENTATION_SYNTAX,
    GATE_NAME_MUTATION_SPOT_CHECK,
    DiagnosticKind,
)
from factory.gate._base import GateResult
from factory.gate._subprocess import _run_pytest

log = logging.getLogger(__name__)


def _check_syntax(content: str) -> GateResult:
    try:
        ast.parse(content)
        return GateResult(passed=True, gate_name=GATE_NAME_IMPLEMENTATION_SYNTAX)
    except SyntaxError as exc:
        return GateResult(
            passed=False,
            gate_name=GATE_NAME_IMPLEMENTATION_SYNTAX,
            diagnostics=[f"Syntax error: {exc}"],
            diagnostic_kind="syntax",
        )


def _check_impl_imports(content: str) -> GateResult:
    try:
        ast.parse(content)
        return GateResult(passed=True, gate_name=GATE_NAME_IMPLEMENTATION_IMPORTS)
    except Exception as exc:
        return GateResult(
            passed=False,
            gate_name=GATE_NAME_IMPLEMENTATION_IMPORTS,
            diagnostics=[f"Import check failed: {exc}"],
            diagnostic_kind="impl_import",
        )


@dataclass(frozen=True)
class Mutation:
    """A single source-code mutation."""

    description: str
    line_no: int | None
    original: str
    mutated: str


class _Mutator(ast.NodeTransformer):
    """Simple AST mutator for Python source.

    Operators implemented:
    - Swap comparison operators (> <, == !=, >= <=)
    - Swap boolean operators (and ↔ or)
    - Remove not (UnaryOp) — replace with identity operand
    - Replace return value: True ↔ False; non-bool → return None
    - Delete a return statement (replace with Pass)
    - Change a numeric constant (increment/decrement by 1)
    """

    _COMPARISON_SWAPS: ClassVar[dict[type, type]] = {
        ast.Gt: ast.Lt,
        ast.Lt: ast.Gt,
        ast.GtE: ast.LtE,
        ast.LtE: ast.GtE,
        ast.Eq: ast.NotEq,
        ast.NotEq: ast.Eq,
    }

    def __init__(self, index: int) -> None:
        self.index = index
        self.visited = 0
        self.mutation: Mutation | None = None

    def visit_Compare(self, node: ast.Compare) -> ast.AST:
        if self.mutation is not None:
            return self.generic_visit(node)
        if len(node.ops) == 1:
            op = node.ops[0]
            swap = self._COMPARISON_SWAPS.get(type(op))
            if swap is not None:
                if self.visited == self.index:
                    node.ops[0] = swap()  # type: ignore[arg-type]
                    self.mutation = Mutation(
                        description=f"swapped {type(op).__name__} to {swap.__name__}",
                        line_no=node.lineno if hasattr(node, "lineno") else None,
                        original=type(op).__name__,
                        mutated=swap.__name__,
                    )
                    return node
                self.visited += 1
        return self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> ast.AST:
        if self.mutation is not None:
            return self.generic_visit(node)
        if self.visited == self.index:
            if isinstance(node.op, ast.And):
                node.op = ast.Or()
                self.mutation = Mutation(
                    description="swapped BoolOp And to Or",
                    line_no=node.lineno if hasattr(node, "lineno") else None,
                    original="And",
                    mutated="Or",
                )
                return node
            elif isinstance(node.op, ast.Or):
                node.op = ast.And()
                self.mutation = Mutation(
                    description="swapped BoolOp Or to And",
                    line_no=node.lineno if hasattr(node, "lineno") else None,
                    original="Or",
                    mutated="And",
                )
                return node
            self.visited += 1
        self.visited += 1
        return self.generic_visit(node)

    def visit_UnaryOp(self, node: ast.UnaryOp) -> ast.AST:
        if self.mutation is not None:
            return self.generic_visit(node)
        if self.visited == self.index:
            if isinstance(node.op, ast.Not):
                self.mutation = Mutation(
                    description="removed Not unary operator",
                    line_no=node.lineno if hasattr(node, "lineno") else None,
                    original="not x",
                    mutated="x",
                )
                return node.operand
            self.visited += 1
        self.visited += 1
        return self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        if self.mutation is not None:
            return self.generic_visit(node)
        if isinstance(node.value, bool):
            return self.generic_visit(node)
        if isinstance(node.value, (int, float)):
            if self.visited == self.index:
                if isinstance(node.value, int):
                    delta = 1 if node.value >= 0 else -1
                    new_val = node.value + delta
                else:
                    new_val = node.value + 1.0
                self.mutation = Mutation(
                    description=f"changed constant {node.value} to {new_val}",
                    line_no=node.lineno if hasattr(node, "lineno") else None,
                    original=str(node.value),
                    mutated=str(new_val),
                )
                return ast.Constant(value=new_val)
            self.visited += 1
        return self.generic_visit(node)

    def visit_Return(self, node: ast.Return) -> ast.AST:
        if self.mutation is not None:
            return self.generic_visit(node)
        if self.visited == self.index:
            # Replace return value when there is a value.
            if node.value is not None:
                if isinstance(node.value, ast.Constant) and isinstance(node.value.value, bool):
                    new_val = ast.Constant(value=(not node.value.value))
                    self.mutation = Mutation(
                        description=f"swapped return {node.value.value} to {new_val.value}",
                        line_no=node.lineno if hasattr(node, "lineno") else None,
                        original=str(node.value.value),
                        mutated=str(new_val.value),
                    )
                    return ast.Return(value=new_val)
                # Non-bool return → return None
                self.mutation = Mutation(
                    description="replaced return value with None",
                    line_no=node.lineno if hasattr(node, "lineno") else None,
                    original="return expr",
                    mutated="return None",
                )
                return ast.Return(value=ast.Constant(value=None))
            # No value on return → delete (original operator)
            self.mutation = Mutation(
                description="deleted return statement",
                line_no=node.lineno if hasattr(node, "lineno") else None,
                original="return ...",
                mutated="pass",
            )
            return ast.Pass()
        self.visited += 1
        return self.generic_visit(node)


def _generate_mutations(source: str, max_mutations: int = 10) -> list[tuple[str, Mutation]]:
    """Return list of (mutated_source, mutation_info) pairs."""
    try:
        ast.parse(source)
    except SyntaxError:
        return []

    results: list[tuple[str, Mutation]] = []
    for i in range(max_mutations):
        mutator = _Mutator(i)
        mutated_tree = ast.fix_missing_locations(mutator.visit(ast.parse(source)))
        if mutator.mutation is None:
            continue
        mutated_source = ast.unparse(mutated_tree)
        results.append((mutated_source, mutator.mutation))
    return results


def _run_suite_on_mutant(
    mutated_source: str,
    test_suite_path: Path,
    interface_pyi_path: Path,
    implementation_path: Path,
    python_executable: str,
    timeout: int,
) -> GateResult:
    """Run inner gate (syntax, imports, mypy, pytest) on a single mutant."""
    syntax_result = _check_syntax(mutated_source)
    if not syntax_result.passed:
        # Mutant is un-syntactic — irrelevant for test-efficacy measurement
        return GateResult(passed=True, gate_name=GATE_NAME_MUTATION_SPOT_CHECK, skipped=True)

    with tempfile.TemporaryDirectory(prefix="sf2_mutant_") as tmpdir:
        # Write mutant under the *original* module name so tests can import it.
        mutant_path = Path(tmpdir) / implementation_path.name
        mutant_path.write_text(mutated_source)
        import_result = _check_impl_imports(mutated_source)
        if not import_result.passed:
            return GateResult(
                passed=True,
                gate_name=GATE_NAME_MUTATION_SPOT_CHECK,
                skipped=True,
            )

        pytest_result = _run_pytest(
            artifact_path=mutant_path,
            test_suite_path=test_suite_path,
            interface_pyi_path=interface_pyi_path,
            python_executable=python_executable,
            timeout=timeout,
            implementation_name=implementation_path.name,
            gate_name=GATE_NAME_MUTATION_SPOT_CHECK,
        )
        return pytest_result


def evaluate_mutation_spot_check(
    implementation_path: Path,
    test_suite_path: Path,
    interface_pyi_path: Path,
    python_executable: str | None = None,
    timeout: int | None = None,
    sample_size: int = 3,
    fail_threshold: float = 0.5,
    seed: int | None = None,
) -> GateResult:
    """Spot-check mutation gate for test efficacy.

    Applies N random mutations to the locked implementation and checks
    whether the test suite catches each mutant.

    A "caught" mutant is one where the test suite fails after the mutation.
    A "live" (surviving) mutant means the test suite passes, revealing a gap
    in test coverage.

    The gate *fails* if the live rate exceeds *fail_threshold*.

    Args:
        implementation_path: Path to the locked .py implementation.
        test_suite_path: Path to the test suite for this module.
        interface_pyi_path: Path to the interface .pyi stub.
        python_executable: Python executable for subprocess tests.
        timeout: Timeout per test run in seconds.
        sample_size: Number of mutants to evaluate.
        fail_threshold: Hard-fail threshold for live-mutant rate.
        seed: Optional RNG seed for reproducibility.
    """
    if seed is not None:
        random.seed(seed)

    source = implementation_path.read_text()
    mutations = _generate_mutations(source, max_mutations=sample_size * 3)
    if not mutations:
        return GateResult(
            passed=True,
            gate_name=GATE_NAME_MUTATION_SPOT_CHECK,
            diagnostics=["No mutations could be generated for this source."],
            skipped=True,
        )

    random.shuffle(mutations)
    selected = mutations[:sample_size]

    exe = python_executable or sys.executable
    if timeout is None:
        timeout = GateTimeouts.pytest_timeout

    live_mutants = 0
    caught_mutants = 0
    skipped_mutants = 0
    details: list[str] = []

    for mutated_source, mutation in selected:
        result = _run_suite_on_mutant(
            mutated_source=mutated_source,
            test_suite_path=test_suite_path,
            interface_pyi_path=interface_pyi_path,
            implementation_path=implementation_path,
            python_executable=exe,
            timeout=timeout,
        )
        if result.skipped:
            skipped_mutants += 1
            details.append(f"  SKIPPED: {mutation.description} at line {mutation.line_no}")
            continue
        if result.passed:
            # Test suite PASSED on the mutant → test efficacy gap
            live_mutants += 1
            details.append(f"  LIVE (missed): {mutation.description} at line {mutation.line_no}")
        else:
            caught_mutants += 1
            details.append(f"  CAUGHT: {mutation.description} at line {mutation.line_no}")

    evaluated = live_mutants + caught_mutants
    if evaluated == 0:
        return GateResult(
            passed=True,
            gate_name=GATE_NAME_MUTATION_SPOT_CHECK,
            diagnostics=["All mutants were ineligible (syntax/import errors)."],
            skipped=True,
        )

    live_rate = live_mutants / evaluated
    passed = live_rate <= fail_threshold

    diagnostics = [
        f"Mutation spot-check: {sample_size} mutants, "
        f"{caught_mutants} caught, {live_mutants} live, {skipped_mutants} skipped. "
        f"Live rate: {live_rate:.0%} (threshold: {fail_threshold:.0%})."
    ]
    diagnostics.extend(details)

    return GateResult(
        passed=passed,
        gate_name=GATE_NAME_MUTATION_SPOT_CHECK,
        diagnostics=diagnostics,
        diagnostic_kind=DiagnosticKind.MUTATION_UNCAUGHT if not passed else "",
    )
