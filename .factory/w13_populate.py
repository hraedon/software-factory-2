#!/usr/bin/env python3
"""W1.3: Populate both workloads via Phase A decomposer and copy fixtures to permanent dirs."""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

from factory.decomposer import decompose_from_spec_md, decompose_from_spec_yaml, write_fixture_files

ROOT_DIR = Path(__file__).resolve().parent.parent

def _do(spec_name: str, source: str) -> None:
    spec_path = ROOT_DIR / "tests" / "fixtures" / spec_name / source
    out_dir = ROOT_DIR / "tests" / "fixtures" / spec_name
    decomposed_dir = out_dir / ".decomposed"

    if decomposed_dir.exists():
        shutil.rmtree(decomposed_dir)
    decomposed_dir.mkdir(parents=True, exist_ok=True)

    if source.endswith(".yaml"):
        result = decompose_from_spec_yaml(spec_path)
    else:
        result = decompose_from_spec_md(spec_path)

    write_fixture_files(result, decomposed_dir)
    print(f"[{spec_name}] Decomposed {source} -> {len(result.modules)} modules in {decomposed_dir}")
    for f in sorted(decomposed_dir.glob("*.md")):
        # Also copy to fixture root for golden-run usage
        dest = out_dir / f.name
        shutil.copy2(f, dest)
        print(f"  copied {f.name}")

    # Validate dependency graph is acyclic
    fr_id_to_mod = {m.fr_id: m for m in result.modules}
    visited = set()
    visiting = set()

    def _has_cycle(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        mod = fr_id_to_mod.get(node)
        for dep in (mod.dependency_fr_ids if mod else []):
            if _has_cycle(dep):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    for m in result.modules:
        if _has_cycle(m.fr_id):
            print(f"  ERROR: cycle detected involving {m.fr_id}")
            sys.exit(1)

    print(f"  OK: acyclic deps validated")


if __name__ == "__main__":
    _do("log-redact-cli", "spec.yaml")
    _do("log-redact-cli", "spec.md")
    _do("dep-graph-viewer", "spec.yaml")
    _do("dep-graph-viewer", "spec.md")
    print("\nAll workloads populated and validated.")
