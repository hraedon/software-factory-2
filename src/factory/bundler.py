from __future__ import annotations

import hashlib
import json
import logging
import re
import shutil
import tarfile
import zipfile
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from factory.workspace import MANIFEST_FILENAME, find_resumable_artifact

_bundler_log = logging.getLogger("factory.bundler")

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    re.IGNORECASE,
)
_RETRY_DIR_RE = re.compile(r"^retry-\d+$")

BUNDLE_VERSION = "1"


@dataclass(frozen=True)
class BundleEntry:
    work_item_id: str
    item_type: str
    module_name: str
    attempt_number: int
    locked_at: str
    artifact_sha256: str
    src_path: str


@dataclass(frozen=True)
class BundleManifest:
    bundle_version: str
    project_name: str
    workflow_version: int
    created_at: str
    work_items: list[BundleEntry]

    def to_dict(self) -> dict:
        return {
            "bundle_version": self.bundle_version,
            "project_name": self.project_name,
            "workflow_version": self.workflow_version,
            "created_at": self.created_at,
            "work_items": [
                {
                    "work_item_id": e.work_item_id,
                    "type": e.item_type,
                    "module_name": e.module_name,
                    "attempt_number": e.attempt_number,
                    "locked_at": e.locked_at,
                    "artifact_sha256": e.artifact_sha256,
                    "src_path": e.src_path,
                }
                for e in self.work_items
            ],
        }


@dataclass
class BundleGateResult:
    passed: bool
    diagnostics: list[str] = field(default_factory=list)
    entry_count: int = 0
    integrity_ok: bool = True


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def collect_artifacts(
    workspace_root: Path,
) -> list[tuple[str, str, Path, str]]:
    entries: list[tuple[str, str, Path, str]] = []
    if not workspace_root.exists():
        return entries
    for work_dir in sorted(workspace_root.iterdir()):
        if not work_dir.is_dir():
            continue
        item_id = work_dir.name
        resumable = find_resumable_artifact(workspace_root, item_id)
        if resumable is None:
            continue
        attempt_number, manifest = resumable
        attempt_path = work_dir / f"attempt-{attempt_number:04d}"
        if not attempt_path.exists():
            continue
        locked_at = manifest.created_at
        for artifact in sorted(attempt_path.iterdir()):
            if artifact.is_dir():
                continue
            if artifact.name == MANIFEST_FILENAME:
                continue
            if artifact.name.startswith("."):
                continue
            if artifact.suffix in (".orig",):
                continue
            entries.append((item_id, "", artifact, locked_at))
        for retry_dir in sorted(attempt_path.iterdir()):
            if not retry_dir.is_dir() or not _RETRY_DIR_RE.match(retry_dir.name):
                continue
            for artifact in sorted(retry_dir.iterdir()):
                if artifact.is_dir():
                    continue
                if artifact.name == MANIFEST_FILENAME:
                    continue
                if artifact.name.startswith("."):
                    continue
                if artifact.suffix in (".orig",):
                    continue
                entries.append((item_id, "", artifact, locked_at))
    return entries


def create_bundle(
    workspace_root: Path,
    project_name: str,
    workflow_version: int,
    output_path: Path,
    output_format: str = "tar.gz",
    include_specs: bool = True,
    include_tests: bool = True,
) -> BundleManifest:
    bundle_dir_name = project_name
    bundle_dir = output_path.parent / f".bundle_tmp_{project_name}"
    if bundle_dir.exists():
        shutil.rmtree(bundle_dir)

    src_dir = bundle_dir / bundle_dir_name / "src"
    tests_dir = bundle_dir / bundle_dir_name / "tests"
    spec_dir = bundle_dir / bundle_dir_name / "spec"
    src_dir.mkdir(parents=True)
    tests_dir.mkdir(parents=True)
    spec_dir.mkdir(parents=True)

    entries: list[BundleEntry] = []
    artifacts = collect_artifacts(workspace_root)

    for item_id, item_type, artifact_path, locked_at in artifacts:
        content = artifact_path.read_bytes()
        sha = _sha256_bytes(content)
        module_name = artifact_path.stem

        dest_dir = src_dir
        if "test" in module_name.lower() or "test_" in artifact_path.name:
            if include_tests:
                dest_dir = tests_dir
            else:
                continue
        elif artifact_path.suffix == ".pyi":
            dest_dir = src_dir

        dest = dest_dir / artifact_path.name
        dest.write_bytes(content)

        entries.append(
            BundleEntry(
                work_item_id=item_id,
                item_type=item_type or "implementation",
                module_name=module_name,
                attempt_number=0,
                locked_at=locked_at or datetime.now(UTC).isoformat(),
                artifact_sha256=sha,
                src_path=str(dest.relative_to(bundle_dir / bundle_dir_name)),
            )
        )

    manifest = BundleManifest(
        bundle_version=BUNDLE_VERSION,
        project_name=project_name,
        workflow_version=workflow_version,
        created_at=datetime.now(UTC).isoformat(),
        work_items=entries,
    )

    manifest_path = bundle_dir / bundle_dir_name / "MANIFEST.json"
    manifest_path.write_text(json.dumps(manifest.to_dict(), indent=2))

    if include_specs:
        spec_src = workspace_root / "spec"
        if spec_src.exists():
            for sf in spec_src.iterdir():
                if sf.is_file():
                    shutil.copy2(str(sf), str(spec_dir / sf.name))

    final_output = output_path
    if output_format == "tar.gz":
        with tarfile.open(str(final_output), "w:gz") as tar:
            tar.add(str(bundle_dir / bundle_dir_name), arcname=bundle_dir_name)
    elif output_format == "zip":
        with zipfile.ZipFile(str(final_output), "w", zipfile.ZIP_DEFLATED) as zf:
            for f in (bundle_dir / bundle_dir_name).rglob("*"):
                if f.is_file():
                    zf.write(str(f), str(f.relative_to(bundle_dir)))
    elif output_format == "dir":
        final_dir = final_output
        if final_dir.exists():
            shutil.rmtree(final_dir)
        shutil.copytree(bundle_dir / bundle_dir_name, final_dir)
    else:
        raise ValueError(f"Unsupported output format: {output_format}")

    shutil.rmtree(bundle_dir, ignore_errors=True)

    _bundler_log.info(
        "bundle_created project=%s items=%d format=%s",
        project_name,
        len(entries),
        output_format,
    )
    return manifest


def verify_bundle_integrity(bundle_path: Path) -> BundleGateResult:
    if not bundle_path.exists():
        return BundleGateResult(
            passed=False,
            diagnostics=[f"Bundle path does not exist: {bundle_path}"],
        )

    if bundle_path.is_dir():
        manifest_path = bundle_path / "MANIFEST.json"
    elif bundle_path.suffix == ".gz" or bundle_path.suffix == ".zip":
        return BundleGateResult(
            passed=True,
            diagnostics=["Archive bundle (skipping inline integrity check)"],
        )
    else:
        return BundleGateResult(
            passed=False,
            diagnostics=[f"Unknown bundle format: {bundle_path}"],
        )

    if not manifest_path.exists():
        return BundleGateResult(
            passed=False,
            diagnostics=["MANIFEST.json not found in bundle"],
        )

    try:
        manifest_data = json.loads(manifest_path.read_text())
    except json.JSONDecodeError as exc:
        return BundleGateResult(
            passed=False,
            diagnostics=[f"Invalid MANIFEST.json: {exc}"],
        )

    items = manifest_data.get("work_items", [])
    errors: list[str] = []
    for item in items:
        src_path = bundle_path / item.get("src_path", "")
        if not src_path.exists():
            errors.append(f"Missing artifact: {item.get('src_path')}")
            continue
        actual_sha = _sha256_file(src_path)
        expected_sha = item.get("artifact_sha256", "")
        if actual_sha != expected_sha:
            errors.append(
                f"Hash mismatch for {item.get('module_name')}: "
                f"expected {expected_sha[:12]}... got {actual_sha[:12]}..."
            )

    return BundleGateResult(
        passed=len(errors) == 0,
        diagnostics=errors,
        entry_count=len(items),
        integrity_ok=len(errors) == 0,
    )
