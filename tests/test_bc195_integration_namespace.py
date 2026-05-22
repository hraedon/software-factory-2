from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from factory.constants import GATE_NAME_INTEGRATION_IMPORT
from factory.gate import evaluate_integration
from factory.gate.integration import _check_unshare, _isolated_cmd


class TestBC195NamespaceIsolation:
    """BC-195: integration subprocess cannot make outbound network connections."""

    @pytest.fixture(autouse=True)
    def _reset_unshare_cache(self):
        import factory.gate.integration as mod

        orig = mod._unshare_available
        mod._unshare_available = None
        yield
        mod._unshare_available = orig

    def test_network_request_in_assembled_tree_fails(self, tmp_path: Path):
        """AC-3: a module that attempts urllib.request.urlopen must fail."""
        artifact = tmp_path / "integration.json"
        artifact.write_text(
            json.dumps(
                {
                    "assembled_tree": {
                        "phone_home.py": (
                            "import urllib.request\n"
                            "urllib.request.urlopen('http://127.0.0.1:1/exfil')\n"
                        ),
                    },
                    "entry_point": "phone_home.run",
                    "integration_tests": "def test_nothing(): pass\n",
                }
            )
        )
        result = evaluate_integration(artifact)
        if _check_unshare():
            assert result.passed is False, (
                "Network request should have failed under unshare --net; "
                f"gate={result.gate_name!r} diagnostics={result.diagnostics}"
            )
            assert result.gate_name == GATE_NAME_INTEGRATION_IMPORT

    def test_isolated_cmd_prepends_unshare_when_available(self):
        cmd = [sys.executable, "-c", "pass"]
        wrapped = _isolated_cmd(cmd)
        if _check_unshare():
            assert wrapped[0] == "unshare"
            assert "--net" in wrapped
            assert "--user" in wrapped
            assert wrapped[-1] == "pass"
        else:
            assert wrapped == cmd

    def test_existing_passing_integration_still_passes(self, tmp_path: Path):
        """AC-4: regression — valid assembled tree still passes with unshare."""
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
            f"Regression: valid tree failed. "
            f"gate={result.gate_name!r} diagnostics={result.diagnostics}"
        )

    def test_no_unshare_graceful_degradation(self, tmp_path: Path, monkeypatch):
        import factory.gate.integration as mod

        monkeypatch.setattr(mod, "_unshare_available", False)
        artifact = tmp_path / "integration.json"
        artifact.write_text(
            json.dumps(
                {
                    "assembled_tree": {
                        "simple.py": "x = 1\n",
                    },
                    "entry_point": "simple.x",
                    "integration_tests": "def test_nothing(): pass\n",
                }
            )
        )
        result = evaluate_integration(artifact)
        assert result.passed is True
