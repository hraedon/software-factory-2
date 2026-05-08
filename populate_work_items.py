#!/usr/bin/env python3
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from substrate import Substrate

ROOT_DIR = Path(__file__).resolve().parent
FIXTURES_DIR = ROOT_DIR / "tests" / "fixtures" / "primary-spec"
SECONDARY_DIR = ROOT_DIR / "tests" / "fixtures" / "secondary-spec"
ROUTING_STRESS_DIR = ROOT_DIR / "tests" / "fixtures" / "routing-stress"

PRIMARY_ITEMS = [
    ("01-acquire_claim.md", "01", "pure-interface", ["AC-06"]),
    ("02-register_workflow.md", "02", "pure-interface", ["AC-17"]),
    ("03-create_link.md", "03", "pure-interface", ["AC-22"]),
    ("04-verify_event_errors.md", "04", "error-taxonomy", ["AC-15", "AC-26"]),
    ("05-acquire_claim_errors.md", "05", "error-taxonomy", ["AC-06"]),
    ("06-transition_errors.md", "06", "error-taxonomy", ["AC-11", "AC-12"]),
    ("07-drift_report.md", "07", "ADT-validation", ["AC-16"]),
    ("08-create_work_item.md", "08", "ADT-validation", ["AC-02"]),
    ("09-query_work_items.md", "09", "ADT-validation", ["AC-05b"]),
    ("10-dead_letter.md", "10", "ADT-validation", ["AC-14"]),
]

ADVERSARIAL_ITEMS = [
    ("AA-adversarial.md", "AA", "adversarial", ["TS-ADV-01", "TS-ADV-02"]),
]

SECONDARY_ITEMS = [
    ("spec.md", "S1", "pure-interface", ["AC-01"]),
    ("spec.md", "S2", "error-taxonomy", ["AC-02"]),
    ("spec.md", "S3", "ADT-validation", ["AC-03"]),
]

ROUTING_STRESS_ITEMS = [
    ("RS-01-type_narrowing.md", "RS1", "pure-interface", ["AC-RS1"]),
    ("RS-02-chunked_process.md", "RS2", "pure-interface", ["AC-RS2"]),
]

ALL_ITEMS = PRIMARY_ITEMS + ADVERSARIAL_ITEMS + SECONDARY_ITEMS + ROUTING_STRESS_ITEMS

DSN = "postgresql://substrate_test:substrate_test@localhost:5432/substrate_test"
KEY_PATH = str(ROOT_DIR / "tests" / "test_keys.json")


def _resolve_spec_text(filename: str, label: str) -> str | None:
    if label.startswith("S"):
        path = SECONDARY_DIR / filename
    elif label.startswith("RS"):
        path = ROUTING_STRESS_DIR / filename
    else:
        path = FIXTURES_DIR / filename
    if not path.exists():
        return None
    return path.read_text()


def _open_or_create_project(
    dsn: str,
    project: str,
    key_path: str,
    workflow_path: Path,
    reset: bool,
    workspace_root: str | None = None,
) -> Substrate:
    if reset:
        from substrate._testing import drop_project_schema

        try:
            drop_project_schema(dsn, project)
        except Exception:
            pass
        if workspace_root:
            ws = Path(workspace_root)
            if ws.exists():
                shutil.rmtree(ws, ignore_errors=True)
                ws.mkdir(parents=True, exist_ok=True)
            print(f"Cleaned workspace '{workspace_root}'")
        print(f"Reset project '{project}'")
    try:
        sub = Substrate.create_project(dsn, project, key_path)
        print(f"Created project '{project}'")
        sub.register_workflow_file(str(workflow_path))
        return sub
    except Exception as e:
        if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
            sub = Substrate(dsn, project, key_path)
            print(f"Connected to existing project '{project}'")
            sub.register_workflow_file(str(workflow_path))
            return sub
        if reset:
            raise
        print(f"ERROR: {e}", file=sys.stderr)
        print("Use --reset to drop and recreate the project.", file=sys.stderr)
        sys.exit(1)


def main():
    from argparse import ArgumentParser

    parser = ArgumentParser(description="Populate SF2 work-items from fixture specs")
    parser.add_argument("--project", default="sf2_test", help="Substrate project name")
    parser.add_argument("--dsn", default=DSN, help="Postgres connection string")
    parser.add_argument("--key-path", default=KEY_PATH, help="Path to HMAC key file")
    parser.add_argument(
        "--reset", action="store_true", help="Drop and recreate the project before populating"
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip work-items that already exist instead of re-creating",
    )
    parser.add_argument(
        "--only",
        type=str,
        default=None,
        help="Comma-separated labels to populate (e.g. '01,AA') — skips all others",
    )
    parser.add_argument(
        "--workspace-root",
        type=str,
        default=None,
        help="Workspace directory to clean on --reset (e.g. /tmp/sf2-golden-001)",
    )
    parser.add_argument(
        "--set",
        type=str,
        default="all",
        choices=["primary", "secondary", "routing-stress", "all"],
        help="Which item set to populate (default: all)",
    )
    parser.add_argument(
        "--workflow",
        type=str,
        default="phase2",
        choices=["phase1", "phase2"],
        help="Workflow version to register (default: phase2)",
    )
    args = parser.parse_args()

    workflow_path = ROOT_DIR / "workflows" / f"{args.workflow}.yaml"
    workflow_version = 1 if args.workflow == "phase1" else 2

    if args.set == "primary":
        items = PRIMARY_ITEMS + ADVERSARIAL_ITEMS
    elif args.set == "secondary":
        items = SECONDARY_ITEMS
    elif args.set == "routing-stress":
        items = ROUTING_STRESS_ITEMS
    else:
        items = ALL_ITEMS

    only_labels = set(args.only.split(",")) if args.only else None

    sub = _open_or_create_project(
        args.dsn, args.project, args.key_path, workflow_path, args.reset, args.workspace_root
    )
    actor_id = "factory-setup"

    created = []
    skipped = 0
    for filename, label, shape, ac_ids in items:
        if only_labels is not None and label not in only_labels:
            skipped += 1
            continue
        spec_text = _resolve_spec_text(filename, label)
        if spec_text is None:
            print(f"  [{label}] SKIP: {filename} not found")
            continue
        try:
            wi, _ = sub.create_work_item(
                workflow_name="software_factory",
                work_item_type="interface_spec",
                actor_id=actor_id,
                custom_fields={
                    "spec_section": spec_text,
                    "ac_ids": ac_ids,
                    "shape": shape,
                },
            )
            created.append((label, shape, str(wi.work_item_id)))
            print(f"  [{label}] {shape:20s} {wi.work_item_id}")
        except Exception as e:
            if "already exists" in str(e).lower() or "duplicate" in str(e).lower():
                print(f"  [{label}] {shape:20s} (already exists, skipping)")
                skipped += 1
            else:
                raise

    print(f"\nCreated {len(created)} work-items, skipped {skipped} existing, "
          f"in project '{args.project}' (workflow_version={workflow_version})")
    print("\nSummary:")
    for label, shape, wi_id in created:
        print(f"  {label}  {shape:20s}  {wi_id}")
    sub.close()


if __name__ == "__main__":
    main()
