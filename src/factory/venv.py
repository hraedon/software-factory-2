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

    Gate tooling (pytest, mypy, ruff) is installed into a separate
    ``<project_dir>/.venv-gate`` to avoid dependency conflicts with project
    requirements.

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
            _clean_stale_project_venv(venv_dir)
            _ensure_gate_venv(project_dir)
            return venv_dir / "bin" / "python"

    has_uv = _which("uv") is not None
    python = sys.executable

    if venv_dir.exists():
        import shutil

        shutil.rmtree(venv_dir)

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

    if requirements.exists() and requirements.stat().st_size > 0:
        if has_uv:
            subprocess.run(
                ["uv", "pip", "install", "--python", str(venv_python), f"-r{requirements}"],
                capture_output=True,
                check=True,
            )
        else:
            subprocess.run(
                [str(venv_python), "-m", "pip", "install", f"-r{requirements}"],
                capture_output=True,
                check=True,
            )

    deps_hash_path.write_text(current_hash)
    _ensure_gate_venv(project_dir)
    return venv_python


_GATE_TOOLS = ["pytest", "mypy", "ruff"]


def _installed_versions_string(gate_python: Path) -> str:
    parts = []
    for tool in _GATE_TOOLS:
        result = subprocess.run(
            [str(gate_python), "-m", "pip", "show", tool],
            capture_output=True,
            text=True,
        )
        version = "unknown"
        for line in result.stdout.splitlines():
            if line.lower().startswith("version:"):
                version = line.split(":", 1)[1].strip()
                break
        parts.append(f"{tool}=={version}")
    return "\n".join(parts) + "\n"


def _gate_tools_hash(gate_python: Path | None = None) -> str:
    hash_input = ",".join(_GATE_TOOLS) + "\n"
    if gate_python is not None and gate_python.exists():
        hash_input += _installed_versions_string(gate_python)
    return hashlib.sha256(hash_input.encode()).hexdigest()


def _clean_stale_project_venv(venv_dir: Path) -> None:
    marker = venv_dir / ".gate_tools_removed"
    if marker.exists():
        return
    for tool in _GATE_TOOLS:
        for suffix in (".dist-info", ".egg-info"):
            for child in venv_dir.glob(f"lib/python*/site-packages/{tool}*{suffix}"):
                shutil.rmtree(child, ignore_errors=True)
    marker.write_text("gate tools moved to .venv-gate")


def _ensure_gate_venv(project_dir: Path) -> Path:
    gate_venv_dir = project_dir / ".venv-gate"
    gate_hash_path = gate_venv_dir / ".gate_hash"
    gate_python = gate_venv_dir / "bin" / "python"

    if gate_venv_dir.exists() and gate_hash_path.exists() and gate_python.exists():
        stored = gate_hash_path.read_text().strip()
        current_gate_hash = _gate_tools_hash(gate_python)
        if stored == current_gate_hash:
            return gate_python

    has_uv = _which("uv") is not None
    python = sys.executable

    if gate_venv_dir.exists():
        shutil.rmtree(gate_venv_dir)

    if has_uv:
        subprocess.run(
            ["uv", "venv", str(gate_venv_dir)],
            capture_output=True,
            check=True,
        )
    else:
        subprocess.run(
            [python, "-m", "venv", str(gate_venv_dir)],
            capture_output=True,
            check=True,
        )

    gate_python = gate_venv_dir / "bin" / "python"
    if has_uv:
        subprocess.run(
            ["uv", "pip", "install", "--python", str(gate_python), *_GATE_TOOLS],
            capture_output=True,
            check=True,
        )
    else:
        subprocess.run(
            [str(gate_python), "-m", "pip", "install", *_GATE_TOOLS],
            capture_output=True,
            check=True,
        )

    post_install_hash = _gate_tools_hash(gate_python)
    gate_hash_path.write_text(post_install_hash)
    return gate_python
