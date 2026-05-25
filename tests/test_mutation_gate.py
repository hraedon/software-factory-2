"""Tests for :mod:`factory.mutation_gate`.

No model invocation — purely mechanical AST mutation and gate logic.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

from factory.constants import GATE_NAME_MUTATION_SPOT_CHECK
from factory.gate._base import GateResult
from factory.mutation_gate import (
    Mutation,
    _generate_mutations,
    _Mutator,
    _run_suite_on_mutant,
    evaluate_mutation_spot_check,
)

SIMPLE_IMPL = """
def max_of(a: int, b: int) -> int:
    if a > b:
        return a
    return b
"""

TEST_SUITE_STRICT = """
import pytest

def test_max_of_basic():
    from impl import max_of
    assert max_of(3, 1) == 3
    assert max_of(1, 3) == 3
    assert max_of(2, 2) == 2
"""

BRANCHED_IMPL = """
def classify(x: int) -> str:
    if x > 10:
        return "big"
    return "small"
"""

TEST_SUITE_LAX = """
def test_classify_small():
    from impl import classify
    assert classify(5) == "small"
"""


def _write_impl_and_tests(tmpdir: Path, impl: str, tests: str) -> tuple[Path, Path]:
    impl_path = tmpdir / "impl.py"
    impl_path.write_text(impl)
    test_path = tmpdir / "test_impl.py"
    test_path.write_text(tests)
    return impl_path, test_path


class TestMutatorAST:
    """Unit-level AST mutation shape tests."""

    def test_comparison_swap(self):
        source = "result = a > b"
        tree = ast.parse(source)
        mutator = _Mutator(index=0)
        mutated = ast.fix_missing_locations(mutator.visit(tree))
        new_source = ast.unparse(mutated)
        assert "a < b" in new_source
        assert mutator.mutation is not None
        assert mutator.mutation.description.startswith("swapped")

    def test_constant_increase(self):
        source = "x = 5"
        tree = ast.parse(source)
        mutator = _Mutator(index=0)
        mutated = ast.fix_missing_locations(mutator.visit(tree))
        new_source = ast.unparse(mutated)
        assert "x = 6" in new_source
        assert mutator.mutation is not None
        assert "changed constant" in mutator.mutation.description

    def test_return_deleted(self):
        source = "def f():\n    return 1\n"
        tree = ast.parse(source)
        mutator = _Mutator(index=0)
        mutated = ast.fix_missing_locations(mutator.visit(tree))
        new_source = ast.unparse(mutated)
        assert "return" not in new_source
        assert mutator.mutation is not None
        assert "deleted return" in mutator.mutation.description

    def test_index_out_of_bounds_no_mutation(self):
        source = "x = 5"
        tree = ast.parse(source)
        mutator = _Mutator(index=999)
        mutator.visit(tree)
        assert mutator.mutation is None


class TestGenerateMutations:
    """Tests for _generate_mutations."""

    def test_generates_multiple_mutations(self):
        muts = _generate_mutations(SIMPLE_IMPL, max_mutations=10)
        assert len(muts) >= 2
        descriptions = {m.description for _, m in muts}
        # Should have at least comparison swap and constant change
        assert any("swapped" in d for d in descriptions)

    def test_max_mutations_respected(self):
        muts = _generate_mutations(SIMPLE_IMPL, max_mutations=2)
        assert len(muts) <= 2

    def test_syntax_error_returns_empty(self):
        muts = _generate_mutations("def bad(", max_mutations=5)
        assert muts == []

    def test_mutation_fields_populated(self):
        muts = _generate_mutations(SIMPLE_IMPL, max_mutations=1)
        assert muts
        _source, mutation = muts[0]
        assert isinstance(mutation, Mutation)
        assert mutation.description
        assert mutation.original
        assert mutation.mutated


class TestRunSuiteOnMutant:
    """Tests for _run_suite_on_mutant gate logic."""

    def test_syntax_error_skipped(self, tmp_path: Path):
        # Create a dummy test file so _run_pytest doesnt crash on missing path
        test_path = tmp_path / "test_dummy.py"
        test_path.write_text("def test_nothing(): pass\n")
        result = _run_suite_on_mutant(
            mutated_source="def bad(",
            test_suite_path=test_path,
            interface_pyi_path=tmp_path / "i.pyi",
            implementation_path=tmp_path / "impl.py",
            python_executable=sys.executable,
            timeout=60,
        )
        assert isinstance(result, GateResult)
        assert result.passed is True
        assert result.skipped is True
        assert result.gate_name == GATE_NAME_MUTATION_SPOT_CHECK

    def test_caught_mutant(self, tmp_path: Path):
        impl_path, test_path = _write_impl_and_tests(tmp_path, SIMPLE_IMPL, TEST_SUITE_STRICT)
        source = impl_path.read_text()
        muts = _generate_mutations(source, max_mutations=10)
        assert muts
        # Pick a comparison-swap mutant — strict tests should catch it
        swap_mutant = None
        for src, mut in muts:
            if "swapped" in mut.description:
                swap_mutant = src
                break
        assert swap_mutant is not None, "No comparison swap mutation generated"
        result = _run_suite_on_mutant(
            mutated_source=swap_mutant,
            test_suite_path=test_path,
            interface_pyi_path=tmp_path / "i.pyi",
            implementation_path=impl_path,
            python_executable=sys.executable,
            timeout=60,
        )
        assert result.passed is False

    def test_live_mutant(self, tmp_path: Path):
        """A mutant that deletes the untested branch should survive lax tests."""
        impl_path, test_path = _write_impl_and_tests(tmp_path, BRANCHED_IMPL, TEST_SUITE_LAX)
        source = impl_path.read_text()
        muts = _generate_mutations(source, max_mutations=10)
        assert muts
        # Find a return-deletion mutation that removes the untested "big" branch.
        # Line numbers: leading newline shifts by 1, so return "big" is at line 4.
        live_mutant = None
        for src, mut in muts:
            if "deleted return" in mut.description and mut.line_no == 4:
                live_mutant = src
                break
        assert live_mutant is not None, (
            "No return-deletion mutation on line 4 (the untested branch)"
        )
        result = _run_suite_on_mutant(
            mutated_source=live_mutant,
            test_suite_path=test_path,
            interface_pyi_path=tmp_path / "i.pyi",
            implementation_path=impl_path,
            python_executable=sys.executable,
            timeout=60,
        )
        assert result.passed is True


class TestEvaluateMutationSpotCheck:
    """Integration-level tests for the full spot-check gate."""

    def test_pass_when_tests_are_strict(self, tmp_path: Path):
        impl_path, test_path = _write_impl_and_tests(tmp_path, SIMPLE_IMPL, TEST_SUITE_STRICT)
        result = evaluate_mutation_spot_check(
            implementation_path=impl_path,
            test_suite_path=test_path,
            interface_pyi_path=tmp_path / "i.pyi",
            sample_size=3,
            fail_threshold=0.5,
            seed=42,
        )
        assert result.passed is True
        assert result.gate_name == GATE_NAME_MUTATION_SPOT_CHECK
        assert "caught" in " ".join(result.diagnostics).lower()

    def test_fail_when_tests_are_lax(self, tmp_path: Path):
        impl_path, test_path = _write_impl_and_tests(tmp_path, BRANCHED_IMPL, TEST_SUITE_LAX)
        result = evaluate_mutation_spot_check(
            implementation_path=impl_path,
            test_suite_path=test_path,
            interface_pyi_path=tmp_path / "i.pyi",
            sample_size=3,
            fail_threshold=0.0,
            seed=42,
        )
        # With fail_threshold=0.0, any live mutant causes a gate fail.
        # The lax test covers only the "small" branch, so deleting the
        # "big" return is a live mutant.
        assert result.passed is False
        assert result.diagnostic_kind == "mutation_uncaught"
        assert "LIVE (missed)" in " ".join(result.diagnostics)

    def test_skipped_when_no_mutations(self, tmp_path: Path):
        impl_path = tmp_path / "impl.py"
        impl_path.write_text("pass")
        test_path = tmp_path / "test_impl.py"
        test_path.write_text("def test_nothing(): pass\n")
        result = evaluate_mutation_spot_check(
            implementation_path=impl_path,
            test_suite_path=test_path,
            interface_pyi_path=tmp_path / "i.pyi",
            sample_size=3,
            seed=42,
        )
        assert result.passed is True
        assert result.skipped is True

    def test_reproducible_with_same_seed(self, tmp_path: Path):
        impl_path, test_path = _write_impl_and_tests(tmp_path, SIMPLE_IMPL, TEST_SUITE_STRICT)
        result_1 = evaluate_mutation_spot_check(
            implementation_path=impl_path,
            test_suite_path=test_path,
            interface_pyi_path=tmp_path / "i.pyi",
            sample_size=3,
            fail_threshold=0.8,
            seed=123,
        )
        result_2 = evaluate_mutation_spot_check(
            implementation_path=impl_path,
            test_suite_path=test_path,
            interface_pyi_path=tmp_path / "i.pyi",
            sample_size=3,
            fail_threshold=0.8,
            seed=123,
        )
        # Same seed should pick the same mutants and produce identical diagnostics
        assert result_1.diagnostics == result_2.diagnostics
