from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from factory.claude_code_channel import ClaudeCodeChannel
from factory.config import FactoryConfig
from factory.constants import (
    ARTIFACT_FILENAME_CANNOT_PROCEED,
    ARTIFACT_FILENAME_RAW_STDOUT,
)


def _golden_run_fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures" / "golden-run-001" / "artifacts"


def _claude_available() -> bool:
    return shutil.which("claude") is not None


def _opencode_available() -> bool:
    return shutil.which("opencode") is not None


FIXTURES_DIR = _golden_run_fixtures_dir()


@pytest.mark.skipif(not _claude_available(), reason="claude CLI not installed")
class TestClaudeSmokeTest:
    def test_claude_version_reachable(self):
        import subprocess

        result = subprocess.run(
            ["claude", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"claude --version failed: {result.stderr}"

    def test_claude_help_reachable(self):
        import subprocess

        result = subprocess.run(
            ["claude", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"claude --help failed: {result.stderr}"


@pytest.mark.skipif(not _opencode_available(), reason="opencode CLI not installed")
class TestOpenCodeSmokeTest:
    def test_opencode_help_reachable(self):
        import subprocess

        result = subprocess.run(
            ["opencode", "--help"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"opencode --help failed: {result.stderr}"


class TestGoldenFileExtraction:
    def _load_fixture(self, work_item_id: str) -> dict[str, str | bytes]:
        fixture_dir = FIXTURES_DIR / work_item_id
        if not fixture_dir.exists():
            pytest.skip(f"fixture {work_item_id} not found")
        raw = (fixture_dir / ARTIFACT_FILENAME_RAW_STDOUT).read_text()
        result: dict[str, str | bytes] = {"raw_stdout": raw}
        manifest_path = fixture_dir / "manifest.json"
        if manifest_path.exists():
            result["manifest"] = json.loads(manifest_path.read_text())
        if (fixture_dir / ARTIFACT_FILENAME_CANNOT_PROCEED).exists():
            result["cannot_proceed"] = json.loads(
                (fixture_dir / ARTIFACT_FILENAME_CANNOT_PROCEED).read_text()
            )
        else:
            result["artifact"] = ""
            for ext in (".pyi", ".py"):
                p = fixture_dir / f"artifact{ext}"
                if p.exists():
                    result["artifact"] = p.read_text()
                    result["artifact_ext"] = ext
                    break
        return result

    def test_fixtures_directory_exists(self):
        assert FIXTURES_DIR.exists(), "golden-run-001 fixtures directory missing"

    def test_extract_interface_spec_artifact(self):
        from factory.output_extraction import extract_artifact_from_output

        fixture = self._load_fixture("2499006e")
        raw = fixture["raw_stdout"]
        artifact = extract_artifact_from_output(raw)
        assert artifact is not None
        assert "def verify_event" in artifact
        assert "class ErrorCode" in artifact

    def test_extract_interface_spec_matches_file(self):
        from factory.output_extraction import extract_artifact_from_output

        fixture = self._load_fixture("2499006e")
        raw = fixture["raw_stdout"]
        artifact = extract_artifact_from_output(raw)
        assert artifact is not None
        saved_artifact = fixture["artifact"].rstrip("\n")
        assert artifact.strip() == saved_artifact.strip()

    def test_cannot_proceed_extraction(self):
        from factory.output_extraction import extract_json_from_output

        fixture = self._load_fixture("74582dcf")
        raw = fixture["raw_stdout"]
        json_data = extract_json_from_output(raw)
        assert json_data is not None
        assert json_data["status"] == "cannot_proceed"
        assert "gaps" in json_data

    def test_cannot_proceed_matches_file(self):
        from factory.output_extraction import extract_json_from_output

        fixture = self._load_fixture("74582dcf")
        raw = fixture["raw_stdout"]
        json_data = extract_json_from_output(raw)
        assert json_data is not None
        saved_cp = fixture["cannot_proceed"]
        assert json_data == saved_cp

    def test_all_interface_spec_fixtures_extractable(self):
        from factory.output_extraction import extract_artifact_from_output

        fixture_ids = [
            d.name for d in FIXTURES_DIR.iterdir() if d.is_dir() and d.name != "74582dcf"
        ]
        for fid in fixture_ids:
            fixture = self._load_fixture(fid)
            raw = fixture["raw_stdout"]
            artifact = extract_artifact_from_output(raw)
            assert artifact is not None, f"fixture {fid}: artifact extraction returned None"


class TestChannelInvokeWithGoldenOutput:
    @pytest.fixture()
    def config(self):
        return FactoryConfig()

    def test_claude_channel_processes_interface_spec_output(self, config, tmp_path):
        fixture = self._load_fixture("2499006e")
        raw_output = fixture["raw_stdout"]
        outputs_dir = tmp_path / "outputs"
        outputs_dir.mkdir()
        (outputs_dir / ARTIFACT_FILENAME_RAW_STDOUT).write_text(raw_output)

        channel = ClaudeCodeChannel(config)
        ext = channel._artifact_extension_for_role("interface_architect")
        assert ext == ".pyi"

        from factory.output_extraction import extract_artifact_from_output

        extracted = extract_artifact_from_output(raw_output)
        assert extracted is not None
        artifact_path = outputs_dir / f"artifact{ext}"
        artifact_path.write_text(extracted + "\n")
        assert artifact_path.exists()
        assert "def verify_event" in artifact_path.read_text()

    def test_claude_channel_processes_cannot_proceed_output(self, config, tmp_path):
        fixture = self._load_fixture("74582dcf")
        raw_output = fixture["raw_stdout"]
        outputs_dir = tmp_path / "outputs"
        outputs_dir.mkdir()
        (outputs_dir / ARTIFACT_FILENAME_RAW_STDOUT).write_text(raw_output)

        from factory.output_extraction import extract_json_from_output

        json_data = extract_json_from_output(raw_output)
        assert json_data is not None
        assert json_data["status"] == "cannot_proceed"

        cp_path = outputs_dir / ARTIFACT_FILENAME_CANNOT_PROCEED
        cp_path.write_text(json.dumps(json_data, indent=2))
        assert cp_path.exists()

        loaded = json.loads(cp_path.read_text())
        assert loaded["status"] == "cannot_proceed"
        assert "gaps" in loaded

    def _load_fixture(self, work_item_id: str) -> dict[str, str | bytes]:
        fixture_dir = FIXTURES_DIR / work_item_id
        if not fixture_dir.exists():
            pytest.skip(f"fixture {work_item_id} not found")
        raw = (fixture_dir / ARTIFACT_FILENAME_RAW_STDOUT).read_text()
        result: dict[str, str | bytes] = {"raw_stdout": raw}
        manifest_path = fixture_dir / "manifest.json"
        if manifest_path.exists():
            result["manifest"] = json.loads(manifest_path.read_text())
        if (fixture_dir / ARTIFACT_FILENAME_CANNOT_PROCEED).exists():
            result["cannot_proceed"] = json.loads(
                (fixture_dir / ARTIFACT_FILENAME_CANNOT_PROCEED).read_text()
            )
        else:
            result["artifact"] = ""
            for ext2 in (".pyi", ".py"):
                p = fixture_dir / f"artifact{ext2}"
                if p.exists():
                    result["artifact"] = p.read_text()
                    result["artifact_ext"] = ext2
                    break
        return result
