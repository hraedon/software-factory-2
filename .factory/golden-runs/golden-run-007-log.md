# Golden Run 007 — BC-072 fix validation (Kimi K2 via Fireworks)

**Date:** 2026-05-10
**Config:** `golden-run-007-config.yaml` (opencode channel, Kimi K2 via Fireworks AI)
**Fixtures:** `tests/fixtures/cert-watch-mini/` (3 interface specs with cross-module dependencies)
**Project:** `sf2_golden_007`

## Purpose

Validate the BC-072 fix for cross-module import resolution in gate temp directories. GR006a (same fixtures, Claude CC) failed with 2/3 test_suites escalated because the gate copied dependency `.pyi` files as `artifact.py` instead of their correct module name (e.g., `certificate_model.py`).

## Code Changes

### 1. BC-072 fix: dependency module name resolution

**Problem:** `_copy_dependency_pyis()` used `dep_path.stem` to derive the module name. Since all artifacts are named `artifact.pyi`, this produced `artifact.py` instead of the correct module name like `certificate_model.py`.

**Fix:** Changed the dependency resolution pipeline to carry module names alongside paths:
- `_resolve_dependency_refs()` in `gate_process.py` now returns `list[tuple[str, Path]]` — each dependency is a `(module_name, path)` pair.
- Module name is derived from the dependency's `spec_section` header: `# Interface Specification: Certificate Model` → `certificate_model`.
- `_extract_module_name_from_spec()` helper added to parse spec titles into valid Python module names.
- `_copy_dependency_pyis()` in `gate.py` now accepts `list[tuple[str, Path]]` and uses the provided module name.
- All gate evaluation functions updated. 5 new tests added.

### 2. populate_work_items.py: role-based transitions + requirements.txt copy

- Fixed `ROLE_NOT_PERMITTED` error: changed actor to `interface_architect` with proper `actor_metadata`.
- Removed `release_claim()` call (transition API handles claim release internally).
- Added `--fixtures` mode: copies `requirements.txt` from fixture dir to workspace root, enabling `ensure_project_venv()` to create a venv with project dependencies.

### 3. Makefile: factory.report → factory.telemetry

### 4. Spec fixture: certificate_model ambiguity fix

AC-08/AC-09 contradicted (union return vs. raise). Fixed AC-09 to say "must return" instead of "must raise".

## Results Summary

| Metric | Value |
|---|---|
| Total work-items | 9 |
| Interface specs locked | 3/3 (100%) |
| Test suites locked | 3/3 (100%) — **including cross-module dependency tests** |
| Implementations locked | 2/3 (67%) |
| Implementations escalated | 1/3 (mypy: incorrect keyword argument) |
| Unknown gate names | 0 |
| Telemetry verify | PASS |

**BC-072 VALIDATED END-TO-END:** Both test_suites AND implementations with `dependency_refs` pointing to `certificate_model` **passed the gate**. The dependency `.pyi` was correctly copied as `certificate_model.py` (derived from spec title) into pytest/mypy temp directories. Cross-module `from certificate_model import Certificate` imports resolved successfully.

## Detailed Item States

| Work Item | Type | State | Notes |
|---|---|---|---|
| `78f26188` | interface_spec | **locked** | certificate_model |
| `7cf5839c` | interface_spec | **locked** | FR-03 file_upload, deps=[certificate_model] |
| `c57ad5fb` | interface_spec | **locked** | FR-02 TLS scan, deps=[certificate_model] |
| `a2e8d69b` | test_suite | **locked** | for certificate_model |
| `7a468775` | test_suite | **locked** | for FR-03, **deps=[certificate_model] resolved** |
| `a6a95a6c` | test_suite | **locked** | for FR-02, **deps=[certificate_model] resolved** |
| `22539000` | implementation | **locked** | for certificate_model |
| `70f7e65a` | implementation | **locked** | for FR-03, **deps=[certificate_model] resolved** |
| `896f797e` | implementation | **cannot_proceed** | for FR-02, mypy: incorrect keyword arg |

## Telemetry

```
  Role                    Channel       Family      Gate                              Hash  Items  1st-Att  Overall  MeanDur
  ----------------------  ------------  ----------  ----------------------------  --------  -----  -------  -------  -------
  implementer             opencode      fireworks   implementation                16f480ba      2       0%     100%   101.2s
  implementer             opencode      fireworks   implementation_mypy           16f480ba      2       0%       0%    70.0s
  interface_architect     opencode      fireworks   interface_spec                45df1cbc      3       0%     100%    26.1s
  test_author             opencode      fireworks   test_suite                    7230fe58      3       0%     100%    84.7s

  Overall: 10 items evaluated, 0% first-attempt pass, 80% overall pass
```

## Comparison to GR006a

| Metric | GR006a (Claude CC) | GR007 (Kimi K2) |
|---|---|---|
| interface_specs | 3/3 (100%) | 3/3 (100%) |
| test_suites (with deps) | 1/3 (33%) — 2 escalated | **3/3 (100%)** — all passed |
| implementations | 1/3 (33%) | **2/3 (67%)** — 1 mypy escalation |
| Total locked | 5/7 (71%) | **8/9 (89%)** |
| Cross-module deps | FAILED | **PASSED** |

## Breadcrumbs

- **BC-072** (cross-module import resolution): Fully resolved and validated. Module name derivation from spec titles + tuple-based dependency resolution working end-to-end for both test_suites and implementations.