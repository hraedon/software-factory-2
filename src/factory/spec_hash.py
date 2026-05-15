from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from factory.constants import CUSTOM_FIELD_SPEC_HASH

_spec_hash_log = logging.getLogger("factory.spec_hash")


@dataclass(frozen=True)
class SpecHash:
    hash_hex: str
    files: list[str]
    computed_at: str


def compute_spec_hash(spec_dir: Path) -> SpecHash:
    if not spec_dir.exists():
        return SpecHash(
            hash_hex="",
            files=[],
            computed_at=datetime.now(UTC).isoformat(),
        )

    h = hashlib.sha256()
    files: list[str] = []
    for spec_file in sorted(spec_dir.iterdir()):
        if spec_file.is_file() and spec_file.suffix in (".md", ".yaml", ".yml"):
            h.update(spec_file.read_bytes())
            files.append(spec_file.name)

    return SpecHash(
        hash_hex=h.hexdigest(),
        files=files,
        computed_at=datetime.now(UTC).isoformat(),
    )


def store_spec_hash(
    sub,
    workflow_run_id: str,
    spec_hash: SpecHash,
) -> None:
    items = sub.query_work_items(
        workflow_run_id=workflow_run_id,
        state="new",
        limit=1,
    )
    if not items:
        items = sub.query_work_items(
            workflow_run_id=workflow_run_id,
            limit=1,
        )
    if items:
        wi = items[0]
        custom = dict(wi.custom_fields or {})
        custom[CUSTOM_FIELD_SPEC_HASH] = spec_hash.hash_hex
        sub.update_work_item(wi.work_item_id, custom_fields=custom)
        _spec_hash_log.info(
            "spec_hash_stored wi=%s hash=%s", wi.work_item_id, spec_hash.hash_hex[:12]
        )


def load_spec_hash(sub, workflow_run_id: str) -> str | None:
    items = sub.query_work_items(workflow_run_id=workflow_run_id, limit=1)
    if not items:
        return None
    custom = items[0].custom_fields or {}
    return custom.get(CUSTOM_FIELD_SPEC_HASH)


@dataclass(frozen=True)
class SpecDiff:
    old_hash: str | None
    new_hash: str
    changed: bool
    summary: str


def compare_spec_hashes(
    old_hash: str | None,
    new_hash: SpecHash,
) -> SpecDiff:
    if old_hash is None:
        return SpecDiff(
            old_hash=None,
            new_hash=new_hash.hash_hex,
            changed=True,
            summary="No previous spec hash found — treating as new spec",
        )
    if old_hash == new_hash.hash_hex:
        return SpecDiff(
            old_hash=old_hash,
            new_hash=new_hash.hash_hex,
            changed=False,
            summary="Spec unchanged",
        )
    return SpecDiff(
        old_hash=old_hash,
        new_hash=new_hash.hash_hex,
        changed=True,
        summary=f"Spec changed (old: {old_hash[:12]}..., new: {new_hash.hash_hex[:12]}...)",
    )
