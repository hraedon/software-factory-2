from __future__ import annotations

from pathlib import Path

from factory.gate import evaluate_test_suite


def test_zero_assertion_fails(tmp_path: Path) -> None:
    content = """
def test_nothing():
    x = 1
"""
    path = tmp_path / "test_zero_assert.py"
    path.write_text(content)
    result = evaluate_test_suite(path)
    assert not result.passed
    assert "test_suite_assertions" in result.gate_name
    assert "zero assertions" in result.diagnostics[0].lower()


def test_one_assertion_passes(tmp_path: Path) -> None:
    content = """
def test_something():
    assert 1 == 1
"""
    path = tmp_path / "test_one_assert.py"
    path.write_text(content)
    result = evaluate_test_suite(path)
    assert result.passed is True


def test_mixed_assertions_fails(tmp_path: Path) -> None:
    content = """
def test_has_assert():
    assert 1 == 1

def test_no_assert():
    x = 2
"""
    path = tmp_path / "test_mixed_assert.py"
    path.write_text(content)
    result = evaluate_test_suite(path)
    assert not result.passed
    assert "test_no_assert" in result.diagnostics[0]


def test_total_assertions_below_function_count_fails(tmp_path: Path) -> None:
    content = """
def test_a():
    assert 1 == 1

def test_b():
    assert 2 == 2

def test_c():
    pass
"""
    path = tmp_path / "test_below_count.py"
    path.write_text(content)
    result = evaluate_test_suite(path)
    # This should be caught by zero-assert check first
    assert not result.passed
    assert "zero assertions" in result.diagnostics[0].lower()


def test_syntax_error_fails_not_passes(tmp_path: Path) -> None:
    content = "def test_broken(:\n    pass\n"
    path = tmp_path / "test_syntax_error.py"
    path.write_text(content)
    result = evaluate_test_suite(path)
    assert not result.passed
    assert "syntax" in result.diagnostic_kind.lower() or result.gate_name == "test_suite_assertions"


def test_no_test_functions_skips_assertion_check(tmp_path: Path) -> None:
    content = """
def helper():
    assert 1 == 1

def test_dummy():
    assert True
"""
    path = tmp_path / "test_no_test_funcs.py"
    path.write_text(content)
    result = evaluate_test_suite(path)
    assert result.passed is True
