from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

from factory.venv import ensure_project_venv


def test_no_requirements_returns_sys_executable(tmp_path: Path) -> None:
    result = ensure_project_venv(tmp_path)
    assert result == Path(sys.executable)


def test_creates_venv_from_requirements(tmp_path: Path) -> None:
    req = tmp_path / "requirements.txt"
    req.write_text("certifi\n")
    exe = ensure_project_venv(tmp_path)
    assert exe.exists()
    assert (tmp_path / ".venv" / ".deps_hash").exists()


def test_reuses_venv_when_hash_unchanged(tmp_path: Path) -> None:
    req = tmp_path / "requirements.txt"
    req.write_text("certifi\n")
    exe1 = ensure_project_venv(tmp_path)
    exe2 = ensure_project_venv(tmp_path)
    assert exe1 == exe2


def test_rebuilds_venv_when_requirements_change(tmp_path: Path) -> None:
    req = tmp_path / "requirements.txt"
    req.write_text("certifi\n")
    ensure_project_venv(tmp_path)
    hash1 = (tmp_path / ".venv" / ".deps_hash").read_text().strip()
    req.write_text("certifi\nidna\n")
    ensure_project_venv(tmp_path)
    hash2 = (tmp_path / ".venv" / ".deps_hash").read_text().strip()
    assert hash1 != hash2


def test_venv_creation_does_not_leak_sensitive_env_vars(tmp_path: Path) -> None:
    req = tmp_path / "requirements.txt"
    req.write_text("certifi\n")
    (tmp_path / ".venv").mkdir(parents=True)
    with (
        patch("factory.venv.run_subprocess") as mock_run,
        patch("factory.venv.shutil.rmtree") as mock_rmtree,
        patch("factory.venv.ensure_gate_venv") as mock_ensure_gate,
    ):
        mock_run.return_value.returncode = 0
        mock_run.return_value.stdout = ""
        mock_run.return_value.stderr = ""
        with patch.dict(
            "os.environ",
            {
                "DATABASE_URL": "secret",
                "MY_API_KEY": "shh",
                "PATH": "/usr/bin",
                "HOME": "/home/user",
            },
            clear=False,
        ):
            ensure_project_venv(tmp_path)

    mock_rmtree.assert_called_once()
    for call in mock_run.call_args_list:
        kwargs = call.kwargs
        env = kwargs.get("env", {})
        assert "DATABASE_URL" not in env
        assert "MY_API_KEY" not in env
        assert "PATH" in env
    assert mock_ensure_gate.called
