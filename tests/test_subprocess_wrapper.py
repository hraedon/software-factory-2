"""Tests for factory.subprocess typed wrapper (RFC-011, Step 1).

The four "missing required kwarg" tests are the load-bearing proof that AC-1 is
satisfied: omitting cwd, env, or timeout_s raises TypeError at call time.
"""

from __future__ import annotations

import pytest

from factory import subprocess as fsubprocess
from factory.subprocess import SubprocessResult, run


class TestRequiredKwargs:
    """AC-1: omitting any required kwarg must raise TypeError at call time."""

    def test_run_requires_cwd_kwarg(self, tmp_path):
        with pytest.raises(TypeError):
            run(cmd=["echo", "x"], env={}, timeout_s=1.0)  # type: ignore[call-arg]

    def test_run_requires_env_kwarg(self, tmp_path):
        with pytest.raises(TypeError):
            run(cmd=["echo", "x"], cwd=tmp_path, timeout_s=1.0)  # type: ignore[call-arg]

    def test_run_requires_timeout_s_kwarg(self, tmp_path):
        with pytest.raises(TypeError):
            run(cmd=["echo", "x"], cwd=tmp_path, env={})  # type: ignore[call-arg]

    def test_run_requires_cmd_kwarg(self, tmp_path):
        with pytest.raises(TypeError):
            run(cwd=tmp_path, env={}, timeout_s=1.0)  # type: ignore[call-arg]


class TestHappyPath:
    def test_run_happy_path_capture(self, tmp_path):
        result = run(cmd=["echo", "hello"], cwd=tmp_path, env={}, timeout_s=5.0)
        assert isinstance(result, SubprocessResult)
        assert result.returncode == 0
        assert "hello" in result.stdout
        assert result.timed_out is False
        assert result.duration_s > 0

    def test_run_captures_stderr(self, tmp_path):
        result = run(
            cmd=["sh", "-c", "echo err >&2; exit 0"],
            cwd=tmp_path,
            env={},
            timeout_s=5.0,
        )
        assert result.returncode == 0
        assert "err" in result.stderr

    def test_run_nonzero_returncode(self, tmp_path):
        result = run(
            cmd=["sh", "-c", "exit 7"],
            cwd=tmp_path,
            env={},
            timeout_s=5.0,
        )
        assert result.returncode == 7
        assert result.timed_out is False

    def test_run_cwd_is_used(self, tmp_path):
        result = run(cmd=["pwd"], cwd=tmp_path, env={}, timeout_s=5.0)
        assert result.returncode == 0
        assert str(tmp_path) in result.stdout.strip()

    def test_run_env_is_used(self, tmp_path):
        # With the var present it should be echoed.
        result_with = run(
            cmd=["sh", "-c", "echo $MY_VAR"],
            cwd=tmp_path,
            env={"MY_VAR": "value42"},
            timeout_s=5.0,
        )
        assert "value42" in result_with.stdout

        # With an empty env the var must be absent — proves no os.environ inheritance.
        result_without = run(
            cmd=["sh", "-c", "echo $MY_VAR"],
            cwd=tmp_path,
            env={},
            timeout_s=5.0,
        )
        assert "value42" not in result_without.stdout

    def test_run_stdin(self, tmp_path):
        result = run(
            cmd=["cat"],
            cwd=tmp_path,
            env={},
            timeout_s=5.0,
            stdin="piped input",
        )
        assert result.returncode == 0
        assert "piped input" in result.stdout


class TestTimeout:
    def test_run_timeout(self, tmp_path):
        result = run(
            cmd=["sleep", "5"],
            cwd=tmp_path,
            env={},
            timeout_s=0.5,
        )
        assert result.timed_out is True
        assert result.returncode != 0
        assert result.duration_s < 2.0


class TestMissingBinary:
    def test_missing_binary_returns_negative_code(self, tmp_path):
        result = run(
            cmd=["__nonexistent_binary_12345__"],
            cwd=tmp_path,
            env={},
            timeout_s=5.0,
        )
        assert result.returncode == -1
        assert result.timed_out is False
        assert "binary not found" in result.stderr


class TestModuleAlias:
    def test_module_importable_as_fsubprocess(self):
        assert hasattr(fsubprocess, "run")
        assert hasattr(fsubprocess, "SubprocessResult")
        assert hasattr(fsubprocess, "clean_env")
