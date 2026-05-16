from __future__ import annotations

import json
from pathlib import Path

from factory.constants import (
    GATE_NAME_INTEGRATION,
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
        assert result.gate_name == GATE_NAME_INTEGRATION

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
        assert result.gate_name == GATE_NAME_INTEGRATION


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
        assert result.gate_name == GATE_NAME_INTEGRATION

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
        assert result.gate_name == GATE_NAME_INTEGRATION


# ---------------------------------------------------------------------------
# BC-175 regression: "Source file found twice" when __init__.py is present
# ---------------------------------------------------------------------------


class TestBC175MypySourceFileTwice:
    """AC-175: integration_mypy must not fail with 'Source file found twice'
    when the assembled tree contains a top-level __init__.py."""

    def test_tree_with_init_py_reaches_real_check_phase(self, tmp_path: Path):
        """Assembled tree with __init__.py and well-typed modules passes mypy gate.

        BC-175: directory target + --explicit-package-bases eliminates the
        dual-resolution collision that previously caused an immediate bail-out.
        """
        artifact = tmp_path / "integration.json"
        artifact.write_text(
            json.dumps(
                {
                    "assembled_tree": {
                        "__init__.py": (
                            "from certificate_model import parse_pem_certificate\n\n"
                            "__all__ = ['parse_pem_certificate']\n"
                        ),
                        "certificate_model.py": (
                            "def parse_pem_certificate(pem: str) -> dict[str, str]:\n"
                            "    return {'pem': pem}\n"
                        ),
                    },
                    "entry_point": "certificate_model.parse_pem_certificate",
                    "integration_tests": (
                        "import certificate_model\n\n"
                        "def test_parse():\n"
                        "    r = certificate_model.parse_pem_certificate('PEM')\n"
                        "    assert r['pem'] == 'PEM'\n"
                    ),
                }
            )
        )
        result = evaluate_integration(artifact)
        # Should pass, NOT fail with "Source file found twice"
        assert result.passed is True, (
            f"Expected integration to pass; got gate={result.gate_name!r} "
            f"diagnostics={result.diagnostics}"
        )
        assert result.gate_name == GATE_NAME_INTEGRATION

    def test_tree_with_init_py_and_type_error_fails_on_real_error(self, tmp_path: Path):
        """With __init__.py present, a real type error must still be caught.

        Ensures BC-175 fix does not accidentally suppress real mypy findings.
        """
        artifact = tmp_path / "integration.json"
        artifact.write_text(
            json.dumps(
                {
                    "assembled_tree": {
                        "__init__.py": "from utils import helper\n",
                        "utils.py": "def helper(x: int) -> int:\n    return x\n",
                        "caller.py": (
                            "import utils\n\n"
                            "def bad() -> str:\n"
                            "    return utils.helper(42)\n"  # int returned as str -> error
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


# ---------------------------------------------------------------------------
# BC-176 regression: ellipsis-body stubs must not trigger [empty-body] errors
# ---------------------------------------------------------------------------


class TestBC176AllowEmptyBodies:
    """AC-176: integration_mypy passes when the assembled tree contains
    ellipsis-body stub functions (interface_architect output style)."""

    def test_ellipsis_stub_passes_mypy_gate(self, tmp_path: Path):
        """A module with def foo() -> str: ... must not fail integration_mypy."""
        artifact = tmp_path / "integration.json"
        artifact.write_text(
            json.dumps(
                {
                    "assembled_tree": {
                        "interface_spec.py": (
                            "def scan_host(host: str) -> dict[str, str]: ...\n"
                            "def upload_cert(pem: str) -> bool: ...\n"
                        ),
                        "impl.py": (
                            "import interface_spec\n\n"
                            "def run(host: str) -> bool:\n"
                            "    result = interface_spec.scan_host(host)\n"
                            "    return bool(result)\n"
                        ),
                    },
                    "entry_point": "impl.run",
                    "integration_tests": (
                        "import impl\n\n"
                        "def test_run_returns_bool():\n"
                        "    assert isinstance(impl.run('x'), bool)\n"
                    ),
                }
            )
        )
        result = evaluate_integration(artifact)
        assert result.passed is True, (
            f"Ellipsis-body stubs caused gate failure: "
            f"gate={result.gate_name!r} diagnostics={result.diagnostics}"
        )

    def test_real_type_error_still_fails_despite_empty_body_flag(self, tmp_path: Path):
        """--allow-empty-bodies must not suppress genuine --strict violations."""
        artifact = tmp_path / "integration.json"
        artifact.write_text(
            json.dumps(
                {
                    "assembled_tree": {
                        "lib.py": "def add(a: int, b: int) -> int:\n    return a + b\n",
                        "caller.py": (
                            "import lib\n\n"
                            "def misuse() -> str:\n"
                            "    return lib.add(1, 2)\n"  # int not compatible with str
                        ),
                    },
                    "entry_point": "caller.misuse",
                    "integration_tests": "def test_nothing(): pass\n",
                }
            )
        )
        result = evaluate_integration(artifact)
        assert result.passed is False
        assert result.gate_name == GATE_NAME_INTEGRATION_MYPY


# ---------------------------------------------------------------------------
# BC-177 regression: hermetic pytest subprocess / no PYTHONPATH leakage
# ---------------------------------------------------------------------------


class TestBC177HermeticPytest:
    """AC-177: integration_pytest must not inherit parent PYTHONPATH and must
    not be shadowed by same-named modules outside the workspace."""

    def test_misleading_parent_pythonpath_does_not_leak(self, tmp_path: Path, monkeypatch):
        """AC-177-a: even if the parent process has PYTHONPATH pointing
        elsewhere, the integration gate resolves from the workspace."""
        # Put a decoy module at a location that would shadow the workspace
        # if PYTHONPATH were inherited.
        decoy_dir = tmp_path / "decoy"
        decoy_dir.mkdir()
        (decoy_dir / "mathlib.py").write_text(
            "def square(x: int) -> int:\n    raise RuntimeError('wrong module')\n"
        )
        monkeypatch.setenv("PYTHONPATH", str(decoy_dir))

        artifact = tmp_path / "integration.json"
        artifact.write_text(
            json.dumps(
                {
                    "assembled_tree": {
                        "mathlib.py": "def square(x: int) -> int:\n    return x * x\n",
                    },
                    "entry_point": "mathlib.square",
                    "integration_tests": (
                        "import mathlib\n\ndef test_square():\n    assert mathlib.square(4) == 16\n"
                    ),
                }
            )
        )
        result = evaluate_integration(artifact)
        assert result.passed is True, (
            f"Gate failed; likely inherited misleading PYTHONPATH. "
            f"gate={result.gate_name!r} diagnostics={result.diagnostics}"
        )

    def test_stray_tmp_module_does_not_shadow_workspace(self, tmp_path: Path):
        """AC-177-b: a stray /tmp/<modname>.py with wrong exports must not
        shadow the assembled workspace copy."""
        import tempfile

        stray = Path(tempfile.gettempdir()) / "cert_shadow_bc177.py"
        try:
            stray.write_text(
                "def parse_pem_certificate(pem: str) -> dict[str, str]:\n"
                "    raise RuntimeError('stray shadow module')\n"
            )

            artifact = tmp_path / "integration.json"
            artifact.write_text(
                json.dumps(
                    {
                        "assembled_tree": {
                            "cert_shadow_bc177.py": (
                                "def parse_pem_certificate(pem: str) -> dict[str, str]:\n"
                                "    return {'ok': pem}\n"
                            ),
                        },
                        "entry_point": "cert_shadow_bc177.parse_pem_certificate",
                        "integration_tests": (
                            "import cert_shadow_bc177\n\n"
                            "def test_parse():\n"
                            "    r = cert_shadow_bc177.parse_pem_certificate('x')\n"
                            "    assert r == {'ok': 'x'}\n"
                        ),
                    }
                )
            )
            result = evaluate_integration(artifact)
            assert result.passed is True, (
                f"Stray /tmp module shadowed workspace. "
                f"gate={result.gate_name!r} diagnostics={result.diagnostics}"
            )
        finally:
            stray.unlink(missing_ok=True)
