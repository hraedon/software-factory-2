from __future__ import annotations

import hashlib
import shutil
import subprocess
import sys
from pathlib import Path


def _which(cmd: str) -> str | None:
    return shutil.which(cmd)


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def ensure_project_venv(project_dir: Path) -> Path:
    """Return the python executable for the per-project venv.

    If ``<project_dir>/requirements.txt`` exists, create/refresh a venv at
    ``<project_dir>/.venv`` from that file.  The venv is rebuilt only when
    the SHA-256 of ``requirements.txt`` changes (recorded in
    ``.venv/.deps_hash``).

    If no ``requirements.txt`` exists, returns ``sys.executable``.

    Uses ``uv`` when available, otherwise falls back to the standard-library
    ``venv`` + ``pip``.
    """
    requirements = project_dir / "requirements.txt"
    if not requirements.exists():
        return Path(sys.executable)

    venv_dir = project_dir / ".venv"
    deps_hash_path = venv_dir / ".deps_hash"
    current_hash = _hash_file(requirements)

    if venv_dir.exists() and deps_hash_path.exists():
        stored_hash = deps_hash_path.read_text().strip()
        if stored_hash == current_hash:
            return venv_dir / "bin" / "python"

    # Determine tooling
    has_uv = _which("uv") is not None
    python = sys.executable

    # Remove stale venv so recreation succeeds
    if venv_dir.exists():
        import shutil

        shutil.rmtree(venv_dir)

    # Create venv
    if has_uv:
        subprocess.run(
            ["uv", "venv", str(venv_dir)],
            capture_output=True,
            check=True,
        )
    else:
        subprocess.run(
            [python, "-m", "venv", str(venv_dir)],
            capture_output=True,
            check=True,
        )

    venv_python = venv_dir / "bin" / "python"

    # Install requirements + gate tooling
    packages = ["pytest", "mypy", "ruff"]
    if requirements.exists() and requirements.stat().st_size > 0:
        packages.append(f"-r{requirements}")

    if has_uv:
        subprocess.run(
            ["uv", "pip", "install", "--python", str(venv_python), *packages],
            capture_output=True,
            check=True,
        )
    else:
        subprocess.run(
            [str(venv_python), "-m", "pip", "install", *packages],
            capture_output=True,
            check=True,
        )

    deps_hash_path.write_text(current_hash)
    return venv_python
