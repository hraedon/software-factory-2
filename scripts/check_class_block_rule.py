#!/usr/bin/env python3
"""Check RFC-030 class-promotion block rule.

Exits non-zero when a CLASS file's instances table has grown while an
open RFC (status: proposed or in_progress) is filed against that class
and no `symptom-fixed-because` rationale is in the CLASS file body.

Usage:
    python scripts/check_class_block_rule.py
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _parse_frontmatter_and_body(text: str) -> tuple[dict, str]:
    """Parse YAML frontmatter and markdown body from a file."""
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    try:
        import yaml
    except ImportError:
        return {}, text
    try:
        fm = yaml.safe_load(parts[1])
    except Exception:
        return {}, text
    body = parts[2].strip()
    return fm if isinstance(fm, dict) else {}, body


def _count_instance_rows(body: str) -> int:
    """Count rows in the instances table under ## Instances."""
    lines = body.splitlines()
    in_table = False
    rows = 0
    for line in lines:
        stripped = line.strip()
        if stripped.lower().startswith("## instances"):
            in_table = True
            continue
        if in_table and stripped.startswith("## "):
            break
        if (
            in_table
            and stripped.startswith("|")
            and "BC" not in stripped
            and "---" not in stripped
            and "#" not in stripped
        ):
            rows += 1
    return rows


def _get_head_text(path: Path) -> str | None:
    """Get file contents at HEAD via git."""
    try:
        result = subprocess.run(
            ["git", "show", f"HEAD:{path}"],
            capture_output=True,
            text=True,
            cwd=str(path.parent.parent),
        )
        if result.returncode == 0:
            return result.stdout
    except Exception:
        pass
    return None


def _find_rfc_status(rfc_name: str, breadcrumbs_dir: Path) -> str | None:
    """Read an RFC file and return its status, or None if not found."""
    # Try both patterns: RFC-NNN-*.md and resolved/RFC-NNN-*.md
    for fname in breadcrumbs_dir.glob(f"*{rfc_name}*"):
        if fname.name.startswith("RFC-"):
            fm, _ = _parse_frontmatter_and_body(fname.read_text())
            return fm.get("status")
    for fname in (breadcrumbs_dir / "resolved").glob(f"*{rfc_name}*"):
        if fname.name.startswith("RFC-"):
            fm, _ = _parse_frontmatter_and_body(fname.read_text())
            return fm.get("status")
    return None


def _has_symptom_fixed_because(body: str) -> bool:
    return "symptom-fixed-because" in body.lower()


def main() -> int:
    repo_root = Path(__file__).parent.parent
    breadcrumbs_dir = repo_root / "breadcrumbs"
    class_files = sorted(breadcrumbs_dir.glob("CLASS-*.md"))

    violations: list[str] = []
    warnings: list[str] = []

    for class_path in class_files:
        fm, body = _parse_frontmatter_and_body(class_path.read_text())
        status = fm.get("status", "").lower()
        if status == "stabilized":
            continue

        _ = fm.get("severity", "low")
        _ = fm.get("title", class_path.name)
        related = fm.get("related", [])

        current_instances = _count_instance_rows(body)
        head_text = _get_head_text(class_path.relative_to(repo_root))
        if head_text is None:
            # New file — can't compare to HEAD; skip this check
            continue
        _head_fm, head_body = _parse_frontmatter_and_body(head_text)
        head_instances = _count_instance_rows(head_body)

        if current_instances <= head_instances:
            continue  # No growth

        if not related:
            continue

        # Find RFCs in related field
        rfc_names = [r for r in related if str(r).upper().startswith("RFC-")]
        if not rfc_names:
            continue

        for rfc_name in rfc_names:
            rfc_status = _find_rfc_status(rfc_name, breadcrumbs_dir)
            if rfc_status is None:
                warnings.append(f"{class_path.name}: references {rfc_name} but file not found")
                continue

            if rfc_status.lower() not in ("proposed", "in_progress"):
                # RFC resolved/implementated/obsolete — block lifted
                continue

            if _has_symptom_fixed_because(body):
                # Explicit rationale written — block lifted
                continue

            violations.append(
                f"{class_path.name} (instances +{current_instances - head_instances}) "
                f"is blocked by {rfc_name} (status: {rfc_status}). "
                f"Add a `symptom-fixed-because` paragraph to the CLASS body, "
                f"drive {rfc_name} to `implemented`, or move the class to `stabilized`."
            )

    if warnings:
        for w in warnings:
            print(f"[WARN] {w}", file=sys.stderr)

    if violations:
        print("[FAIL] RFC-030 class-promotion block rule violations found:", file=sys.stderr)
        for v in violations:
            print(f"  - {v}", file=sys.stderr)
        return 1

    print("[PASS] No RFC-030 class-promotion block rule violations.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
