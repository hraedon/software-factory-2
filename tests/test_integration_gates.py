from __future__ import annotations

import json
from pathlib import Path

from factory.constants import (
    GATE_NAME_INTEGRATION_IMPORT,
    GATE_NAME_INTEGRATION_MYPY,
    GATE_NAME_INTEGRATION_PYTEST,
)
from factory.gate import evaluate_integration


class TestEvaluateIntegrationImport:
    def _tree(self, mod_b: str):
        return {
            "module_a.py": "def add(a: int, b: int) -> int:\n    return a + b\n\n",
            "module_b.py": mod_b,
        }

    def test_valid_assembled_tree_passes(self, tmp_path: Path):
        artifact = tmp_path / "integration.json"
        artifact.write_text(
            json.dumps(
                {
                    "assembled_tree": self._tree(
                        "import module_a\n\n"
                        "def compute(x: int) -> int:\n"
                        "    return module_a.add(x, x)\n"
                    ),
                    "entry_point": "module_b.compute",
                    "integration_tests": (
                        "\n"
                        "import module_a\n"
                        "import module_b\n\n"
                        "def test_cross_module():\n"
                        "    assert module_b.compute(3) == 6\n"
                    ),
                }
            )
        )
        result = evaluate_integration(artifact)
        assert result.passed is True
        assert result.gate_name == GATE_NAME_INTEGRATION_IMPORT

    def test_invalid_json_fails(self, tmp_path: Path):
        artifact = tmp_path / "integration.json"
        artifact.write_text("not json")
        result = evaluate_integration(artifact)
        assert result.passed is False
        assert result.gate_name == GATE_NAME_INTEGRATION_IMPORT
        assert "not valid JSON" in result.diagnostics[0]
        assert result.diagnostic_kind == "integration_import"

    def test_missing_assembled_tree_fails(self, tmp_path: Path):
        artifact = tmp_path / "integration.json"
        artifact.write_text(json.dumps({"entry_point": "foo"}))
        result = evaluate_integration(artifact)
        assert result.passed is False
        assert "missing 'assembled_tree'" in result.diagnostics[0]

    def test_import_error_in_module_fails(self, tmp_path: Path):
        artifact = tmp_path / "integration.json"
        artifact.write_text(
            json.dumps(
                {
                    "assembled_tree": {"bad.py": "import nonexistent_module\n"},
                    "entry_point": "bad.main",
                    "integration_tests": "def test_nothing(): pass\n",
                }
            )
        )
        result = evaluate_integration(artifact)
        assert result.passed is False
        assert result.gate_name == GATE_NAME_INTEGRATION_IMPORT
        assert "Import resolution failed" in result.diagnostics[0]
        assert result.diagnostic_kind == "integration_import"

    def test_deep_module_paths(self, tmp_path: Path):
        artifact = tmp_path / "integration.json"
        artifact.write_text(
            json.dumps(
                {
                    "assembled_tree": {
                        "pkg/__init__.py": "",
                        "pkg/sub.py": "def value() -> int:\n    return 1\n",
                    },
                    "entry_point": "pkg.sub.value",
                    "integration_tests": "def test_nothing(): pass\n",
                }
            )
        )
        result = evaluate_integration(artifact)
        assert result.passed is True


class TestEvaluateIntegrationMypy:
    def test_mypy_type_error_fails(self, tmp_path: Path):
        artifact = tmp_path / "integration.json"
        artifact.write_text(
            json.dumps(
                {
                    "assembled_tree": {
                        "typed.py": "def greet(name: str) -> str:\n    return name\n",
                        "caller.py": (
                            "import typed\n\ndef bad() -> str:\n    return typed.greet(123)\n"
                        ),
                    },
                    "entry_point": "caller.bad",
                    "integration_tests": "def test_nothing(): pass\n",
                }
            )
        )
        result = evaluate_integration(artifact)
        assert result.passed is False
        assert result.gate_name == GATE_NAME_INTEGRATION_MYPY
        assert result.diagnostic_kind == "integration_mypy"

    def test_mypy_clean_tree_passes(self, tmp_path: Path):
        artifact = tmp_path / "integration.json"
        artifact.write_text(
            json.dumps(
                {
                    "assembled_tree": {
                        "typed.py": "def greet(name: str) -> str:\n    return name\n",
                        "caller.py": (
                            "import typed\n\ndef good() -> str:\n    return typed.greet('world')\n"
                        ),
                    },
                    "entry_point": "caller.good",
                    "integration_tests": "def test_nothing(): pass\n",
                }
            )
        )
        result = evaluate_integration(artifact)
        assert result.passed is True
        assert result.gate_name == GATE_NAME_INTEGRATION_IMPORT


class TestEvaluateIntegrationPytest:
    def test_pytest_failure_fails(self, tmp_path: Path):
        artifact = tmp_path / "integration.json"
        artifact.write_text(
            json.dumps(
                {
                    "assembled_tree": {
                        "mathlib.py": "def square(x: int) -> int:\n    return x * x\n",
                    },
                    "entry_point": "mathlib.square",
                    "integration_tests": (
                        "\n"
                        "import mathlib\n\n"
                        "def test_square():\n"
                        "    assert mathlib.square(4) == 9999\n"
                    ),
                }
            )
        )
        result = evaluate_integration(artifact)
        assert result.passed is False
        assert result.gate_name == GATE_NAME_INTEGRATION_PYTEST
        assert result.diagnostic_kind == "integration_pytest"

    def test_no_integration_tests_skips_pytest(self, tmp_path: Path):
        artifact = tmp_path / "integration.json"
        artifact.write_text(
            json.dumps(
                {
                    "assembled_tree": {
                        "mathlib.py": "def square(x: int) -> int:\n    return x * x\n",
                    },
                    "entry_point": "mathlib.square",
                }
            )
        )
        result = evaluate_integration(artifact)
        assert result.passed is True

    def test_empty_integration_tests_skips_pytest(self, tmp_path: Path):
        artifact = tmp_path / "integration.json"
        artifact.write_text(
            json.dumps(
                {
                    "assembled_tree": {
                        "mathlib.py": "def square(x: int) -> int:\n    return x * x\n",
                    },
                    "entry_point": "mathlib.square",
                    "integration_tests": "",
                }
            )
        )
        result = evaluate_integration(artifact)
        assert result.passed is True

    def test_integration_tests_pass(self, tmp_path: Path):
        artifact = tmp_path / "integration.json"
        artifact.write_text(
            json.dumps(
                {
                    "assembled_tree": {
                        "mathlib.py": "def square(x: int) -> int:\n    return x * x\n",
                    },
                    "entry_point": "mathlib.square",
                    "integration_tests": (
                        "\n"
                        "import mathlib\n\n"
                        "def test_square():\n"
                        "    assert mathlib.square(4) == 16\n"
                    ),
                }
            )
        )
        result = evaluate_integration(artifact)
        assert result.passed is True


class TestEvaluateIntegrationPromotion:
    """Mechanical promotion of flat assembled_tree into package directory."""

    def test_flat_init_with_relative_imports_gets_promoted(self, tmp_path: Path):
        artifact = tmp_path / "integration.json"
        artifact.write_text(
            json.dumps(
                {
                    "assembled_tree": {
                        "__init__.py": "from .mathlib import square\n",
                        "mathlib.py": "def square(x: int) -> int:\n    return x * x\n",
                    },
                    "entry_point": "mathlib.square",
                    "integration_tests": (
                        "\n"
                        "import mathlib\n\n"
                        "def test_square():\n"
                        "    assert mathlib.square(4) == 16\n"
                    ),
                }
            )
        )
        result = evaluate_integration(artifact)
        assert result.passed is True
        assert result.gate_name == GATE_NAME_INTEGRATION_IMPORT

    def test_flat_init_without_relative_imports_stays_flat(self, tmp_path: Path):
        artifact = tmp_path / "integration.json"
        artifact.write_text(
            json.dumps(
                {
                    "assembled_tree": {
                        "__init__.py": "# package init\n",
                        "interface.py": "def square(x: int) -> int:\n    return x * x\n",
                    },
                    "entry_point": "interface.square",
                    "integration_tests": (
                        "\n"
                        "import interface\n\n"
                        "def test_square():\n"
                        "    assert interface.square(4) == 16\n"
                    ),
                }
            )
        )
        result = evaluate_integration(artifact)
        assert result.passed is True
        assert result.gate_name == GATE_NAME_INTEGRATION_IMPORT
