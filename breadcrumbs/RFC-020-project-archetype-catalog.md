---
number: "RFC-020"
title: "Project archetype catalog for Phase 5 cold-start"
severity: high
status: proposed
kind: design
author: opencode-review
date: "2026-05-13"
tags: [catalog, archetypes, stage-0, fixtures, phase-5, dep-v1-300]
related: ["RFC-010", "RFC-019"]
phase_needed: "Phase 5 (first real workload)"
---

## Problem

v1 had BC-300: *"Infrastructure pattern library: validated project archetypes agents instantiate."* The catalog lived under `factory/catalog/` with entries for FastAPI, Postgres, Entra, and Windows — each a YAML file describing placement, provided symbols, required dependencies, and skeleton constraints.

v2's fixtures (cert-watch) are hand-curated. For Phase 5 "pick a small LoB tool," there is no story for the cold-start skeleton: what `pyproject.toml` should the factory emit? What directory structure? What base dependencies? The principal currently authors all of this by hand in the fixture.

Spec §10 Phase 6 gestures at *"patterns extracted into reusable roles/skills"* — but that is bottom-up pattern recognition from completed workloads. v1 found you also want **top-down archetypes**: CLI tool, web service, data pipeline. Without them, every new project starts from a blank page, and the skeleton architect (v1's role, not v2's) speculates into a vacuum.

## Scope

### In scope (Phase 5 MVP)

1. **Archetype definitions**
   Three initial archetypes, each a directory under `catalog/`:
   - `cli-tool/` — single entry point, `argparse` or `click`, no web server.
   - `web-service/` — FastAPI/Flask, async handler pattern, one `main.py` + `routes/`.
   - `library-module/` — no entry point, installable package, `src/<name>/` layout.

2. **Per-archetype contents**
   Each archetype directory contains:
   - `archetype.yaml` — metadata (name, version, compatible_phases, required_roles).
   - `skeleton/` — directory tree copied to the workspace root before Stage 2.
     - `pyproject.toml` with correct `[project]`, `[tool.pytest.ini_options]`, dependencies.
     - `src/` or `<name>/` with `__init__.py`.
     - `requirements.txt` (optional, for non-poetry workflows).
     - `README.md` template with placeholders.
   - `prompt_addendum.md` — role-specific instructions appended to the interface architect prompt when this archetype is selected (e.g., "use `argparse` for CLI tools").

3. **Archetype selection**
   - `--archetype <name>` flag on `populate_work_items.py`.
   - Defaults from `FactoryConfig.archetype_name` (default: `cli-tool` for Phase 5 safety).
   - If `--fixtures` is used and the fixture directory contains an `archetype.yaml`, that takes precedence (fixture is a full override).

4. **Validation**
   - `pytest` on a generated skeleton passes (empty but importable).
   - `ruff check` on the skeleton passes (no lint errors in boilerplate).

### Out of scope (future phases)

- Composable archetypes (mix-and-match database + framework + auth). v1 attempted this and the combinatorial scaling was adversarially reviewed as problematic.
- Docker Compose snippets or infrastructure bringup (v1 `catalog/infra/`).
- Platform-specific entries (Windows, macOS).
- Versioned archetype evolution or migration tooling.

## Design

### `catalog/` directory layout

```
catalog/
  cli-tool/
    archetype.yaml
    skeleton/
      pyproject.toml
      src/
        __init__.py
      README.md
    prompt_addendum.md
  web-service/
    ...
  library-module/
    ...
```

### `archetype.yaml` schema

```yaml
name: cli-tool
version: 1
compatible_phases: [1, 2, 3, 4, 5]
required_roles: [interface_architect, test_author, implementer]
dependencies:
  - pytest
  - ruff
  - mypy
entry_point: "src/{module_name}/cli.py"
test_pattern: "tests/test_{module_name}.py"
```

Placeholders like `{module_name}` are substituted at skeleton-copy time from `populate_work_items.py`'s derived module names.

### Integration with `populate_work_items.py`

When `--archetype <name>` is provided:
1. Load `catalog/<name>/archetype.yaml`.
2. Validate that `required_roles` ⊆ config roles.
3. Copy `catalog/<name>/skeleton/` to `workspace_root`.
4. Substitute placeholders (`{module_name}`, `{project_name}`) in all skeleton files.
5. Append `prompt_addendum.md` content to each role's prompt context (via `context.py`).
6. Proceed with spec parsing and work-item creation as normal.

### Relationship to RFC-010 (fixture taxonomy)

RFC-010 classifies *test fixtures* by architectural complexity class (A: single-module, B: linear chain, C: diamond deps, D: full DAG).

RFC-020 provides *project archetypes* (cold-start skeletons) independent of fixture class. A fixture may override the archetype entirely (cert-watch has its own skeleton), but a real Phase 5 workload would use an archetype + a spec, with no hand-curated fixture.

## Phase placement

Phase 5 prerequisite. The first real workload needs a starting shape.

## Validation criteria

1. `populate_work_items.py --archetype cli-tool --project_name mytool` creates `workspace_root/mytool/src/mytool/__init__.py` and importable skeleton.
2. `pytest` on the generated skeleton passes (zero tests, zero failures — just importability).
3. `ruff check` on the skeleton passes.
4. The interface architect prompt includes the `cli-tool` addendum when the archetype is selected.
5. Fixture-driven runs (cert-watch) are unaffected when `--archetype` is absent.

## Open questions

1. Should archetypes support multi-language (TypeScript, Rust)? Not for Phase 5. Python only.
2. Should archetype selection be inferred from the spec (e.g., if spec mentions "REST API," auto-select `web-service`)? Defer to Phase 6. Phase 5 is explicit `--archetype`.
3. Should the catalog live in-repo or as a separate package? In-repo keeps it versioned with the factory.

## Precedent

- v1 BC-300: *"Infrastructure pattern library: validated project archetypes agents instantiate."*
- v1 `factory/catalog/frameworks/fastapi/catalog.yaml` — framework entry with provided symbols and deps.
- v1 adversarial review of catalog combinatorics: *"Composing catalog entries by concern rather than bundling monolithic entries"* — RFC-020 avoids bundling by using minimal, non-composable archetypes.
