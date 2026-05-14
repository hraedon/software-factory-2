from __future__ import annotations

import subprocess
from pathlib import Path
from typing import ClassVar
from unittest.mock import patch

from factory.config import FactoryConfig
from factory.constants import ARTIFACT_FILENAME_RAW_STDERR, ARTIFACT_FILENAME_RAW_STDOUT
from factory.subprocess_channel import SubprocessChannel


class _TestChannel(SubprocessChannel):
    CMD: ClassVar[list[str]] = ["echo", "test"]
    _NAME = "test-channel"
    _DEFAULT_FAMILY = "test"

    def _derive_invocation_family(self, role_config) -> str:
        return "test"

    def _build_cmd(self, role_config) -> list[str]:
        return list(self.CMD)


def _make_config(**overrides) -> FactoryConfig:
    defaults = {"workspace_root": Path("/tmp/test-ws")}
    defaults.update(overrides)
    return FactoryConfig(**defaults)


def _mock_completed_process(
    returncode: int = 0, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(
        args=["echo", "test"], returncode=returncode, stdout=stdout, stderr=stderr
    )


class TestEmptyOutputStderrCapture:
    def test_stderr_included_in_error_message(self, tmp_path):
        config = _make_config(empty_output_retries=0)
        channel = _TestChannel(config)
        outputs = tmp_path / "out"

        with patch("factory.subprocess_channel.subprocess.run") as mock_run:
            mock_run.return_value = _mock_completed_process(
                stdout="", stderr="API rate limit exceeded"
            )
            result = channel.invoke("implementer", "prompt", outputs, 60)

        assert not result.success
        assert "Empty output from echo" in result.error_message
        assert "API rate limit exceeded" in result.error_message

    def test_raw_stderr_file_written(self, tmp_path):
        config = _make_config(empty_output_retries=0)
        channel = _TestChannel(config)
        outputs = tmp_path / "out"

        with patch("factory.subprocess_channel.subprocess.run") as mock_run:
            mock_run.return_value = _mock_completed_process(
                stdout="", stderr="some diagnostic info"
            )
            channel.invoke("implementer", "prompt", outputs, 60)

        stderr_file = outputs / ARTIFACT_FILENAME_RAW_STDERR
        assert stderr_file.exists()
        assert stderr_file.read_text() == "some diagnostic info"

    def test_raw_stdout_file_written_on_empty(self, tmp_path):
        config = _make_config(empty_output_retries=0)
        channel = _TestChannel(config)
        outputs = tmp_path / "out"

        with patch("factory.subprocess_channel.subprocess.run") as mock_run:
            mock_run.return_value = _mock_completed_process(stdout="", stderr="")
            channel.invoke("implementer", "prompt", outputs, 60)

        assert (outputs / ARTIFACT_FILENAME_RAW_STDOUT).exists()

    def test_no_stderr_no_crash(self, tmp_path):
        config = _make_config(empty_output_retries=0)
        channel = _TestChannel(config)
        outputs = tmp_path / "out"

        with patch("factory.subprocess_channel.subprocess.run") as mock_run:
            mock_run.return_value = _mock_completed_process(stdout="", stderr=None)
            result = channel.invoke("implementer", "prompt", outputs, 60)

        assert not result.success
        assert "Empty output" in result.error_message

    def test_stderr_truncated_at_500_chars(self, tmp_path):
        config = _make_config(empty_output_retries=0)
        channel = _TestChannel(config)
        outputs = tmp_path / "out"
        long_stderr = "x" * 1000

        with patch("factory.subprocess_channel.subprocess.run") as mock_run:
            mock_run.return_value = _mock_completed_process(stdout="", stderr=long_stderr)
            result = channel.invoke("implementer", "prompt", outputs, 60)

        assert not result.success
        assert len(result.error_message) < 600


class TestEmptyOutputRetry:
    def test_retry_succeeds_on_second_attempt(self, tmp_path):
        config = _make_config(empty_output_retries=1, empty_output_retry_delay_seconds=0)
        channel = _TestChannel(config)
        outputs = tmp_path / "out"

        with (
            patch("factory.subprocess_channel.subprocess.run") as mock_run,
            patch("factory.subprocess_channel.time.sleep"),
        ):
            mock_run.side_effect = [
                _mock_completed_process(stdout=""),
                _mock_completed_process(stdout="```python\ndef foo() -> int:\n    return 1\n```"),
            ]
            result = channel.invoke("implementer", "prompt", outputs, 60)

        assert result.success
        assert result.artifact_name == "artifact.py"
        assert mock_run.call_count == 2

    def test_all_retries_exhausted(self, tmp_path):
        config = _make_config(empty_output_retries=2, empty_output_retry_delay_seconds=0)
        channel = _TestChannel(config)
        outputs = tmp_path / "out"

        with (
            patch("factory.subprocess_channel.subprocess.run") as mock_run,
            patch("factory.subprocess_channel.time.sleep"),
        ):
            mock_run.return_value = _mock_completed_process(stdout="", stderr="timeout")
            result = channel.invoke("implementer", "prompt", outputs, 60)

        assert not result.success
        assert "Empty output" in result.error_message
        assert mock_run.call_count == 3

    def test_zero_retries_no_retry(self, tmp_path):
        config = _make_config(empty_output_retries=0)
        channel = _TestChannel(config)
        outputs = tmp_path / "out"

        with patch("factory.subprocess_channel.subprocess.run") as mock_run:
            mock_run.return_value = _mock_completed_process(stdout="")
            result = channel.invoke("implementer", "prompt", outputs, 60)

        assert not result.success
        assert mock_run.call_count == 1

    def test_non_empty_output_skips_retry(self, tmp_path):
        config = _make_config(empty_output_retries=3, empty_output_retry_delay_seconds=0)
        channel = _TestChannel(config)
        outputs = tmp_path / "out"

        with patch("factory.subprocess_channel.subprocess.run") as mock_run:
            mock_run.return_value = _mock_completed_process(
                stdout="```python\ndef foo() -> int:\n    return 1\n```"
            )
            result = channel.invoke("implementer", "prompt", outputs, 60)

        assert result.success
        assert mock_run.call_count == 1

    def test_non_zero_exit_skips_retry(self, tmp_path):
        config = _make_config(empty_output_retries=3, empty_output_retry_delay_seconds=0)
        channel = _TestChannel(config)
        outputs = tmp_path / "out"

        with patch("factory.subprocess_channel.subprocess.run") as mock_run:
            mock_run.return_value = _mock_completed_process(returncode=1, stderr="fatal error")
            result = channel.invoke("implementer", "prompt", outputs, 60)

        assert not result.success
        assert mock_run.call_count == 1

    def test_timeout_skips_retry(self, tmp_path):
        config = _make_config(empty_output_retries=3, empty_output_retry_delay_seconds=0)
        channel = _TestChannel(config)
        outputs = tmp_path / "out"

        with patch("factory.subprocess_channel.subprocess.run") as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired(cmd="echo", timeout=60)
            result = channel.invoke("implementer", "prompt", outputs, 60)

        assert not result.success
        assert result.timed_out
        assert mock_run.call_count == 1

    def test_retry_delay_called(self, tmp_path):
        config = _make_config(empty_output_retries=1, empty_output_retry_delay_seconds=5)
        channel = _TestChannel(config)
        outputs = tmp_path / "out"

        with (
            patch("factory.subprocess_channel.subprocess.run") as mock_run,
            patch("factory.subprocess_channel.time.sleep") as mock_sleep,
        ):
            mock_run.side_effect = [
                _mock_completed_process(stdout=""),
                _mock_completed_process(stdout="```python\nx = 1\n```"),
            ]
            channel.invoke("implementer", "prompt", outputs, 60)

        mock_sleep.assert_called_once_with(5)

    def test_raw_stdout_reflects_last_attempt(self, tmp_path):
        config = _make_config(empty_output_retries=1, empty_output_retry_delay_seconds=0)
        channel = _TestChannel(config)
        outputs = tmp_path / "out"

        with (
            patch("factory.subprocess_channel.subprocess.run") as mock_run,
            patch("factory.subprocess_channel.time.sleep"),
        ):
            mock_run.side_effect = [
                _mock_completed_process(stdout=""),
                _mock_completed_process(stdout="```python\ndef foo() -> int:\n    return 1\n```"),
            ]
            channel.invoke("implementer", "prompt", outputs, 60)

        raw = (outputs / ARTIFACT_FILENAME_RAW_STDOUT).read_text()
        assert "def foo" in raw
