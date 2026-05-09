from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

GR006A_TELEMETRY_PATH = Path("/tmp/sf2-gr006a/telemetry.json")
GR006A_ARTIFACTS_PATH = Path("/tmp/sf2-gr006a/artifacts.json")


def gr006a_results_present() -> bool:
    return GR006A_TELEMETRY_PATH.exists()


def load_gr006a_telemetry() -> dict:
    return json.loads(GR006A_TELEMETRY_PATH.read_text())


def load_gr006a_artifacts() -> dict:
    return json.loads(GR006A_ARTIFACTS_PATH.read_text())


def test_gr006a_meets_phase2_exit_threshold() -> None:
    """GR006a must achieve >= 70% implementation lock rate
    across FR-02 and FR-03 to declare Phase 2 complete."""
    if not gr006a_results_present():
        pytest.skip("GR006a not yet executed")
    impl_pass_rate = load_gr006a_telemetry()["implementation_pass_rate"]
    assert impl_pass_rate >= 0.70


def test_gr006a_produces_no_unknown_gate_names() -> None:
    if not gr006a_results_present():
        pytest.skip("GR006a not yet executed")
    assert load_gr006a_telemetry()["unknown_gate_rate"] == 0.0


def test_gr006a_cross_module_imports_resolve() -> None:
    if not gr006a_results_present():
        pytest.skip("GR006a not yet executed")
    assert load_gr006a_artifacts()["cross_module_import_success"]


def test_gr006a_telemetry_verify_passes() -> None:
    if not gr006a_results_present():
        pytest.skip("GR006a not yet executed")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "factory.telemetry",
            "--verify",
            "--config",
            "golden-run-006a-config.yaml",
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
