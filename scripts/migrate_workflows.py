#!/usr/bin/env python3
"""Verify and manage workflow composition migration.

Verifies that the composed workflow YAMLs produce semantically equivalent
WorkflowDefinitions to the pre-migration monolithic versions.

Usage:
    python scripts/migrate_workflows.py --verify    # verify composed files
    python scripts/migrate_workflows.py --restore   # restore monolithic backups
    python scripts/migrate_workflows.py --status     # show current file status
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOWS_DIR = REPO_ROOT / "workflows"
BACKUP_DIR = WORKFLOWS_DIR / ".pre_migration_backup"

PHASE_FILES = [
    "phase1.yaml",
    "phase2.yaml",
    "phase3.yaml",
    "phase4.yaml",
    "phase5.yaml",
]


def verify_semantic() -> bool:
    from regista import parse_file

    all_ok = True
    for fname in PHASE_FILES:
        backup_path = BACKUP_DIR / fname
        new_path = WORKFLOWS_DIR / fname
        if not backup_path.exists():
            print(f"  SKIP {fname} — no backup to compare")
            continue

        try:
            old_wf = parse_file(str(backup_path))
            new_wf = parse_file(str(new_path))
        except Exception as e:
            print(f"  {fname}: PARSE ERROR — {e}")
            all_ok = False
            continue

        checks = []

        if old_wf.version != new_wf.version:
            print(f"  {fname}: version mismatch {old_wf.version} != {new_wf.version}")
            checks.append(False)

        if set(old_wf.roles) != set(new_wf.roles):
            print(f"  {fname}: roles mismatch {set(old_wf.roles)} != {set(new_wf.roles)}")
            checks.append(False)

        if set(old_wf.states) != set(new_wf.states):
            print(f"  {fname}: states mismatch")
            checks.append(False)

        old_wit = {w.name for w in old_wf.work_item_types}
        new_wit = {w.name for w in new_wf.work_item_types}
        if old_wit != new_wit:
            print(f"  {fname}: work_item_types mismatch {old_wit} != {new_wit}")
            checks.append(False)

        for ow in old_wf.work_item_types:
            for nw in new_wf.work_item_types:
                if ow.name == nw.name:
                    if {f.name for f in ow.custom_fields} != {f.name for f in nw.custom_fields}:
                        print(f"  {fname}: wit '{ow.name}' custom_fields mismatch")
                        checks.append(False)

        old_lt = {(l.name, l.source_type, l.target_type) for l in old_wf.link_types}
        new_lt = {(l.name, l.source_type, l.target_type) for l in new_wf.link_types}
        if old_lt != new_lt:
            print(f"  {fname}: link_types mismatch")
            checks.append(False)

        old_trans = {(t.name, t.from_state): set(t.allowed_roles) for t in old_wf.transitions}
        new_trans = {(t.name, t.from_state): set(t.allowed_roles) for t in new_wf.transitions}
        if old_trans != new_trans:
            print(f"  {fname}: transitions mismatch")
            checks.append(False)

        if old_wf.attempt_threshold != new_wf.attempt_threshold:
            print(f"  {fname}: attempt_threshold mismatch")
            checks.append(False)

        status = "OK" if all(checks) else "MISMATCH"
        print(f"  {fname}: {status}")
        if not all(checks):
            all_ok = False

    return all_ok


def restore_originals() -> None:
    if not BACKUP_DIR.exists():
        print("No backup directory found. Cannot restore.")
        sys.exit(1)
    for fname in PHASE_FILES:
        src = BACKUP_DIR / fname
        dst = WORKFLOWS_DIR / fname
        if src.exists():
            shutil.copy2(src, dst)
            print(f"  Restored {fname}")
    print("Restore complete.")


def show_status() -> None:
    import yaml

    for fname in PHASE_FILES:
        path = WORKFLOWS_DIR / fname
        if not path.exists():
            print(f"  {fname}: MISSING")
            continue
        data = yaml.safe_load(path.read_text())
        extends = data.get("extends", "(none)")
        version = data.get("version", "?")
        print(f"  {fname}: v{version}, extends={extends}")


def main() -> None:
    args = sys.argv[1:]
    if "--restore" in args:
        restore_originals()
        return
    if "--status" in args:
        show_status()
        return
    if "--verify" in args:
        print("Verifying composed workflows against monolithic backups...\n")
        if verify_semantic():
            print("\nAll semantic checks pass.")
        else:
            print("\nSome semantic checks failed!")
            sys.exit(1)
        return
    print("Usage: migrate_workflows.py [--verify|--restore|--status]")


if __name__ == "__main__":
    main()