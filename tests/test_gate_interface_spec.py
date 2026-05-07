from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from factory.gate import evaluate_interface_spec, structural_signature, structurally_equivalent_pyi


@pytest.fixture()
def artifact_dir(tmp_path):
    return tmp_path


def _write_stub(artifact_dir: Path, name: str, content: str) -> Path:
    p = artifact_dir / name
    p.write_text(textwrap.dedent(content))
    return p


class TestInterfaceSpecHappyPath:
    def test_valid_pyi(self, artifact_dir):
        stub = _write_stub(
            artifact_dir,
            "test.pyi",
            '''
from typing import Union

def parse_range(input: str, today: date) -> Union[Range, Error]:
    """Satisfies AC-01, AC-02."""
    ...
''',
        )
        result = evaluate_interface_spec(stub, ac_ids=["AC-01", "AC-02"])
        assert result.passed
        assert result.artifact_valid

    def test_valid_pyi_no_ac_ids(self, artifact_dir):
        stub = _write_stub(
            artifact_dir,
            "test.pyi",
            """
def foo(x: int) -> str: ...
""",
        )
        result = evaluate_interface_spec(stub)
        assert result.passed


class TestInterfaceSpecSyntaxError:
    def test_syntax_error(self, artifact_dir):
        stub = _write_stub(
            artifact_dir,
            "bad.pyi",
            """
def foo( -> int: ...
""",
        )
        result = evaluate_interface_spec(stub)
        assert not result.passed
        assert result.gate_name == "interface_spec_syntax"
        assert "SyntaxError" in result.diagnostics[0]


class TestInterfaceSpecStubCheck:
    def test_implementation_body(self, artifact_dir):
        stub = _write_stub(
            artifact_dir,
            "impl.py",
            """
def foo(x: int) -> str:
    return str(x)
""",
        )
        result = evaluate_interface_spec(stub)
        assert not result.passed
        assert "implementation body" in result.diagnostics[0]


class TestInterfaceSpecACReference:
    def test_missing_ac_reference(self, artifact_dir):
        stub = _write_stub(
            artifact_dir,
            "test.pyi",
            '''
def foo(x: int) -> str:
    """Satisfies AC-01."""
    ...
''',
        )
        result = evaluate_interface_spec(stub, ac_ids=["AC-01", "AC-02"])
        assert not result.passed
        assert result.gate_name == "interface_spec_ac_references"
        assert "AC-02" in result.diagnostics[0]

    def test_all_acs_present(self, artifact_dir):
        stub = _write_stub(
            artifact_dir,
            "test.pyi",
            '''
def foo(x: int) -> str:
    """Satisfies AC-01, AC-02."""
    ...
''',
        )
        result = evaluate_interface_spec(stub, ac_ids=["AC-01", "AC-02"])
        assert result.passed


class TestInterfaceSpecFileNotFound:
    def test_missing_file(self, artifact_dir):
        missing = artifact_dir / "nonexistent.pyi"
        result = evaluate_interface_spec(missing)
        assert not result.passed
        assert result.gate_name == "interface_spec_file_exists"

    def test_empty_file(self, artifact_dir):
        stub = _write_stub(artifact_dir, "empty.pyi", "")
        result = evaluate_interface_spec(stub)
        assert not result.passed
        assert result.gate_name == "interface_spec_not_empty"


class TestStructuralEquivalence:
    def test_identical_content_is_equivalent(self):
        content = '''
from dataclasses import dataclass
from typing import Union

@dataclass(frozen=True)
class Foo:
    """Satisfies AC-01."""
    x: int

def bar(y: str) -> Foo:
    """Satisfies AC-01."""
    ...
'''
        assert structurally_equivalent_pyi(content, content)

    def test_formatting_differences_ignored(self):
        a = '''
from dataclasses import dataclass
from typing import Union

@dataclass(frozen=True)
class Foo:
    """Satisfies AC-01."""
    x: int

Result = Union[Foo, None]

def bar(y: str) -> Result:
    """Satisfies AC-01, AC-02."""
    ...
'''
        b = '''
from typing import Union
from dataclasses import dataclass

Result = Union[Foo, None]

@dataclass(frozen=True)
class Foo:
    """Successful. Satisfies AC-01."""
    x: int

def bar(y: str) -> Result:
    """Satisfies AC-01, AC-02.

    Some extra prose here about implementation details.
    """
    ...
'''
        assert structurally_equivalent_pyi(a, b)

    def test_different_function_names_not_equivalent(self):
        a = '''
def acquire_claim(x: int) -> bool:
    """Satisfies AC-06."""
    ...
'''
        b = '''
def acquire(x: int) -> bool:
    """Satisfies AC-06."""
    ...
'''
        assert not structurally_equivalent_pyi(a, b)

    def test_different_parameter_types_not_equivalent(self):
        a = '''
def foo(x: int) -> str:
    """Satisfies AC-01."""
    ...
'''
        b = '''
def foo(x: str) -> int:
    """Satisfies AC-01."""
    ...
'''
        assert not structurally_equivalent_pyi(a, b)

    def test_different_enum_members_not_equivalent(self):
        a = '''
from enum import Enum

class ErrorCode(Enum):
    """Satisfies AC-01."""
    A = "a"
    B = "b"
'''
        b = '''
from enum import Enum

class ErrorCode(Enum):
    """Satisfies AC-01."""
    A = "a"
    C = "c"
'''
        assert not structurally_equivalent_pyi(a, b)

    def test_extra_function_not_equivalent(self):
        a = '''
def foo(x: int) -> str:
    """Satisfies AC-01."""
    ...
'''
        b = '''
def foo(x: int) -> str:
    """Satisfies AC-01."""
    ...

def bar(y: str) -> int:
    """Satisfies AC-02."""
    ...
'''
        assert not structurally_equivalent_pyi(a, b)

    def test_different_ac_references_not_equivalent(self):
        a = '''
def foo(x: int) -> str:
    """Satisfies AC-01."""
    ...
'''
        b = '''
def foo(x: int) -> str:
    """Satisfies AC-01, AC-02."""
    ...
'''
        assert not structurally_equivalent_pyi(a, b)

    def test_same_ac_different_docstring(self):
        a = '''
def foo(x: int) -> str:
    """Satisfies AC-01, AC-02."""
    ...
'''
        b = '''
def foo(x: int) -> str:
    """Does important things. Satisfies AC-02, AC-01, and more."""
    ...
'''
        assert structurally_equivalent_pyi(a, b)

    def test_syntax_error_returns_false(self):
        assert not structurally_equivalent_pyi("def foo(: ...", "def foo(x: int): ...")

    def test_structural_signature_roundtrip(self):
        content = '''
from enum import Enum
from dataclasses import dataclass

class E(Enum):
    X = "x"

@dataclass(frozen=True)
class D:
    a: int

Alias = Union[D, E]

def f(p: int) -> Alias:
    """Satisfies AC-07."""
    ...
'''
        sig = structural_signature(content)
        assert "class:D" in sig
        assert "class:E" in sig
        assert "enum_member:E.X='x'" in sig
        assert any("fn:f" in s for s in sig)
        assert any("type_alias:Alias" in s for s in sig)
