from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path


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
