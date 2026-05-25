from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

WORK_DIR_NAME = ".factory"
WORK_SUBDIR = "work"
CORRUPT_DIR_NAME = ".corrupt"
MANIFEST_FILENAME = "manifest.json"


@dataclass(frozen=True)
class ArtifactManifest:
    attempt_number: int
    work_item_id: str
    artifact_name: str
    artifact_sha256: str
    artifact_size: int
    actor_id: str | None = None
    channel: str | None = None
    model: str | None = None
    family: str | None = None
    context_hash: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


def _validate_path_component(value: str, label: str) -> str:
    if "/" in value or "\\" in value or ".." in value:
        raise ValueError(f"Invalid {label}: {value!r} (path traversal detected)")
    return value


def attempt_dir(work_root_path: Path, work_item_id: str, attempt_number: int) -> Path:
    _validate_path_component(work_item_id, "work_item_id")
    return work_root_path / work_item_id / f"attempt-{attempt_number:04d}"


def write_artifact(
    attempt_path: Path,
    artifact_name: str,
    data: bytes,
    manifest: ArtifactManifest,
) -> Path:
    _validate_path_component(artifact_name, "artifact_name")
    attempt_path.mkdir(parents=True, exist_ok=True)
    dest = attempt_path / artifact_name
    tmp = attempt_path / f".{artifact_name}.tmp"
    tmp.write_bytes(data)
    os.replace(tmp, dest)
    manifest_data = json.dumps(manifest.__dict__, indent=2, sort_keys=True)
    manifest_tmp = attempt_path / f".{MANIFEST_FILENAME}.tmp"
    manifest_tmp.write_text(manifest_data)
    manifest_dest = attempt_path / MANIFEST_FILENAME
    os.replace(manifest_tmp, manifest_dest)
    return dest


def compute_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_manifest(manifest_path: Path) -> ArtifactManifest | None:
    if not manifest_path.exists():
        return None
    try:
        raw = json.loads(manifest_path.read_text())
        return ArtifactManifest(**raw)
    except (json.JSONDecodeError, TypeError, KeyError):
        return None


def _validate_attempt(attempt_path: Path) -> ArtifactManifest | None:
    manifest_path = attempt_path / MANIFEST_FILENAME
    manifest = _read_manifest(manifest_path)
    if manifest is None:
        return None
    artifact_path = attempt_path / manifest.artifact_name
    if not artifact_path.exists():
        return None
    artifact_data = artifact_path.read_bytes()
    actual_hash = compute_sha256(artifact_data)
    if actual_hash != manifest.artifact_sha256:
        return None
    if len(artifact_data) != manifest.artifact_size:
        return None
    return manifest


def find_resumable_artifact(
    work_root_path: Path,
    work_item_id: str,
) -> tuple[int, ArtifactManifest] | None:
    _validate_path_component(work_item_id, "work_item_id")
    item_dir = work_root_path / work_item_id
    if not item_dir.exists():
        return None
    candidates: list[tuple[int, ArtifactManifest]] = []
    for entry in sorted(item_dir.iterdir()):
        if not entry.is_dir() or entry.is_symlink():
            continue
        if entry.name.startswith(".") or entry.name == CORRUPT_DIR_NAME:
            continue
        if not entry.name.startswith("attempt-"):
            continue
        try:
            attempt_number = int(entry.name.split("-", 1)[1])
        except (ValueError, IndexError):
            continue
        manifest = _validate_attempt(entry)
        if manifest is not None:
            candidates.append((attempt_number, manifest))
    if not candidates:
        return None
    return max(candidates, key=lambda c: c[0])


def quarantine_attempt(attempt_path: Path) -> Path:
    parent = attempt_path.parent
    corrupt_dir = parent / CORRUPT_DIR_NAME
    corrupt_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
    attempt_name = attempt_path.name
    dest = corrupt_dir / f"{attempt_name}-{timestamp}"
    if dest.exists():
        counter = 1
        while True:
            alt = corrupt_dir / f"{attempt_name}-{timestamp}-{counter}"
            if not alt.exists():
                dest = alt
                break
            counter += 1
    os.replace(attempt_path, dest)
    return dest


def list_attempt_dirs(work_root_path: Path, work_item_id: str) -> list[Path]:
    _validate_path_component(work_item_id, "work_item_id")
    item_dir = work_root_path / work_item_id
    if not item_dir.exists():
        return []
    dirs: list[Path] = []
    for entry in sorted(item_dir.iterdir()):
        if entry.is_dir() and entry.name.startswith("attempt-"):
            dirs.append(entry)
    return dirs
