from __future__ import annotations

import sys
from pathlib import Path

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
