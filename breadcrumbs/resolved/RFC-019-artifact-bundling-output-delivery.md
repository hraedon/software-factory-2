---
number: "RFC-019"
title: "Artifact bundling and output delivery — Stage 9 implementation"
severity: high
status: implemented
kind: design
author: opencode-review
date: "2026-05-13"
tags: [stage-9, output, delivery, phase-5, dep-v1-provisioner]
related: ["RFC-017", "RFC-020"]
phase_needed: "Phase 5 (first real workload)"
---

## Problem

Spec §4 Stage 9 says: *"Outcome verification → Runs the assembled software end-to-end against AC → Produces artifact bundle for principal."*

Stage 10 says: *"Principal review → Does the running software do what was asked? → Yes → ship."*

There is no module in v2 that implements either of these. The pipeline stops at Stage 8 (integration). The principal has no defined interaction surface for receiving the output of a completed workload.

v1 had `github_provisioner.py` (creates repos, pushes code, configures CI) and `stub_issues.py` (tracks stub-related work). v2 intentionally shed v1's complexity, but the Phase 5 exit criteria cannot be met without answering: *the principal gets what, exactly?*

## Scope

### In scope (Phase 5 MVP)

1. **Artifact bundling** (`factory/bundler.py`)
   - Collects all locked implementation artifacts across work items.
   - Verifies each artifact has a valid manifest (SHA-256 matches on-disk content).
   - Produces a bundle with:
     - `src/` directory containing all `.py` locked implementations, organized by module name.
     - `tests/` directory containing all locked test suites.
     - `spec/` directory containing the original spec files.
     - `MANIFEST.json` — list of included work items with IDs, attempt numbers, SHA-256s, and lock timestamps.
   - Output formats: `.tar.gz` (default), `.zip` (for Windows principal), or plain directory tree.

2. **Bundle gate**
   - A mechanical gate that runs *before* bundling:
     - All implementation work items in the DAG are locked.
     - No `cannot_proceed` items exist.
     - All manifest hashes match.
     - `pytest` passes on the assembled `src/` + `tests/` tree.
   - This is a Phase 5 gate and counts toward the mechanical gate budget.

3. **CLI entry point**
   - `factory bundle --config <yaml> --output <path> [--format tar.gz|zip|dir]`
   - Fails with diagnostic if bundle gate fails.

### Out of scope (future phases)

- GitHub repository creation or Git remote push (v1's `github_provisioner.py`). Worth adopting if the principal targets GitHub, but not Phase 5 MVP.
- GitHub Issues generation from spec functional requirements.
- CI/CD workflow templates.
- Automatic PR creation against a target repo.
- Artifact signing or attestation.

## Design

### Bundle structure

```
<bundle-name>/
  MANIFEST.json           # Bundle manifest
  src/
    <module_a>.py         # From locked implementation work items
    <module_b>.py
    <module_b>_deps/
      <dep>.py            # Dependency implementations (if dep_resolution says so)
  tests/
    test_<module_a>.py    # From locked test_suite work items
    test_<module_b>.py
  spec/
    spec.md               # Original spec
    spec.yaml             # Machine-readable sidecar (if exists)
```

### Manifest schema

```json
{
  "bundle_version": "1",
  "factory_version": "2.x",
  "project_name": "cert-watch",
  "workflow_version": 3,
  "created_at": "2026-05-13T14:32:00Z",
  "work_items": [
    {
      "work_item_id": "wi_001",
      "type": "implementation",
      "module_name": "event_parser",
      "attempt_number": 2,
      "locked_at": "2026-05-13T14:15:00Z",
      "artifact_sha256": "abc123...",
      "src_path": "src/event_parser.py"
    }
  ]
}
```

### Bundle gate

The bundle gate is a new mechanical gate (`evaluate_bundle`) with these checks:

1. **Completeness**: every leaf implementation work item in the DAG is in `locked` state.
2. **Integrity**: each artifact's on-disk SHA-256 matches its manifest.
3. **Determinism**: `pytest` on the assembled tree passes with zero failures.
4. **No orphans**: every test in `tests/` has a corresponding implementation in `src/` (by module name convention).

This gate counts as 1 mechanical gate toward the Phase 5 budget of 18.

### Integration with dep_resolution.py

`bundler.py` delegates module placement to `dep_resolution.py`'s existing `resolve_dep_artifacts()`. If a dependency is a stub-only module, the bundle includes the `.pyi` file; if it has a locked implementation, the `.py` file. The bundle gate verifies this resolution produces a valid import graph.

## Configuration

```python
@dataclass
class BundleConfig:
    output_format: str = "tar.gz"
    include_specs: bool = True
    include_tests: bool = True
    bundle_dir_name: str | None = None  # defaults to project_name
```

## Phase placement

Phase 5 prerequisite. Without bundling, Stage 9 is a no-op and the principal cannot review or ship.

## Validation criteria

1. On a completed golden run, `factory bundle --output /tmp/cert-watch-bundle.tar.gz` produces a valid archive.
2. Extracting the archive and running `pytest` in the extracted directory passes.
3. `MANIFEST.json` validates against a JSON schema (tests included).
4. Bundle gate fails if any implementation is not locked.
5. Bundle gate fails if any manifest hash mismatches.

## Open questions

1. Should the bundle include the `pyproject.toml` / `requirements.txt` from the workspace? Yes — the principal needs to be able to install and run the result.
2. Should the bundle include `.factory/` metadata (checkpoints, worklogs)? No — principal-facing output is the artifact only. Metadata stays in the project directory.
3. Should bundling be automatic on pipeline completion or manual CLI? Phase 5: manual CLI. Automation can come later.

## Precedent

- v1 `factory/github_provisioner.py` — creates repos and pushes initial code. The GitHub-specific parts are out of scope; the "produce a shippable artifact" part is the core of this RFC.
- v1 `factory/stub_issues.py` — the `.stub-issue` convention is not adopted; v2's failure routing replaces it.
- v2 `workspace.py` — manifest format and content-addressing are reusable.
