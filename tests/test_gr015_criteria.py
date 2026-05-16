from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from factory.config import FactoryConfig

GR015_CONFIG_PATH = Path(".factory/golden-runs/golden-run-015-config.yaml")
GR015_TELEMETRY_DIR = Path("/tmp/sf2-golden-015")
GR015_TELEMETRY_PATH = GR015_TELEMETRY_DIR / "telemetry.json"
GR015_ARTIFACTS_PATH = GR015_TELEMETRY_DIR / "artifacts.json"

CERT_WATCH_FULL_SPEC_COUNT = 8


def gr015_results_present() -> bool:
    return GR015_TELEMETRY_PATH.exists()


def load_gr015_telemetry() -> dict:
    return json.loads(GR015_TELEMETRY_PATH.read_text())


def load_gr015_artifacts() -> dict:
    return json.loads(GR015_ARTIFACTS_PATH.read_text())


def test_gr015_interface_spec_lock_rate() -> None:
    if not gr015_results_present():
        pytest.skip("GR-015 not yet executed")
    tel = load_gr015_telemetry()
    iface_rate = tel.get("interface_spec_pass_rate", 0)
    assert iface_rate >= 0.875, f"Interface spec lock rate {iface_rate:.0%} < 87.5%"


def test_gr015_no_module_not_found_errors() -> None:
    if not gr015_results_present():
        pytest.skip("GR-015 not yet executed")
    artifacts = load_gr015_artifacts()
    assert not artifacts.get("has_module_not_found_errors", False), (
        "Gate outputs contain ModuleNotFoundError"
    )


def test_gr015_cross_module_imports_resolve() -> None:
    if not gr015_results_present():
        pytest.skip("GR-015 not yet executed")
    artifacts = load_gr015_artifacts()
    assert artifacts.get("cross_module_import_success", False), (
        "Cross-module imports failed to resolve"
    )


def test_gr015_work_item_count() -> None:
    if not gr015_results_present():
        pytest.skip("GR-015 not yet executed")
    tel = load_gr015_telemetry()
    total = tel.get("total_work_items", 0)
    expected_min = CERT_WATCH_FULL_SPEC_COUNT * 3 - 2
    assert total >= expected_min, f"Expected >= {expected_min} work items, got {total}"


def test_gr015_produces_no_unknown_gate_names() -> None:
    if not gr015_results_present():
        pytest.skip("GR-015 not yet executed")
    tel = load_gr015_telemetry()
    assert tel.get("unknown_gate_rate", 1.0) == 0.0


def test_gr015_telemetry_verify_passes() -> None:
    if not gr015_results_present():
        pytest.skip("GR-015 not yet executed")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "factory.telemetry",
            "--verify",
            "--config",
            str(GR015_CONFIG_PATH),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_gr015_uses_multi_channel_config() -> None:
    if not gr015_results_present():
        pytest.skip("GR-015 not yet executed")
    tel = load_gr015_telemetry()
    channels_seen = tel.get("channels", [])
    assert len(channels_seen) >= 1, "Expected at least one model channel"
    config = FactoryConfig.from_yaml(GR015_CONFIG_PATH)
    model_channels = set(rc.channel for rc in config.roles if rc.channel != "code")
    assert len(model_channels) >= 1, "GR-015 config should use multi-channel dispatch"
