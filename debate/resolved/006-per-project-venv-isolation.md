---
number: "006"
title: "Per-project venv isolation — prevent environment pollution in subprocess gates"
author: opencode
date: "2026-05-09"
related: ["RFC-006", "BC-059"]
---

## Context

v2's mechanical gates invoke tooling via `sys.executable -m` or `shutil.which("ruff")`. This means they run in the **factory's own Python environment**. When Phase 5 begins building real line-of-business tools, generated code will declare dependencies (e.g., `requests`, `pydantic`, `fastapi`) that are not installed in the factory venv. The gates will fail with `ModuleNotFoundError` even when the implementation and tests are correct.

v1 solved this with per-project venv isolation (BC-192: *"Each factory project gets `.factory/venv/` — no more cross-project package collisions"*). v2 has no equivalent.

## Problem

The current gate process is environment-coupled. A test suite that imports `pydantic` will fail the pytest gate because `pydantic` is not in the factory venv. The implementer cannot fix this by changing code — it's a deployment gap. This creates false-negative gate failures that route back to the implementer, wasting model budget on unfixable problems.

## Position

**Build per-project venv isolation before Phase 5, but do not over-engineer it.** A simple, cacheable venv per project is sufficient.

### Proposed design

1. **Venv location:** `.factory/venv/<project_id>/` (or per-work-item if projects share IDs)
2. **Dependency discovery:** Parse `requirements.txt` or `pyproject.toml` from generated artifacts. If none exists, use an empty venv.
3. **Tool installation:** Install `pytest`, `mypy`, `ruff` into the project venv via `pip install` on first use.
4. **Gate invocation:** Prefix subprocess commands with the project venv's Python binary:
   ```python
   venv_python = venv_dir / "bin" / "python"
   subprocess.run([venv_python, "-m", "pytest", ...], ...)
   ```
5. **Caching:** If `requirements.txt` hash hasn't changed, reuse existing venv.

### Why not the factory venv

The factory venv contains regista, psycopg, structlog, and other dependencies the generated code should not import. Running generated code in the factory venv is a sandbox violation. It also means generated projects can accidentally depend on factory-internal packages without declaring them.

### Relationship to BC-059

BC-059 fixed gate soft-fail on missing tooling by switching to `sys.executable -m`. This was correct for Phase 2 (no external deps) but creates the environment-coupling problem for Phase 5. The fix is not to revert BC-059 but to layer venv isolation on top of it.

## Risks

| Risk | Mitigation |
|---|---|
| Venv creation is slow (~10-30s) | Cache venvs; only recreate when dependencies change |
| Generated code has undeclared dependencies | The venv is empty except for tools; undeclared deps fail fast and correctly, routing to spec ambiguity |
| Cross-platform venv paths (Windows vs Linux) | Use `sys.executable` discovery within venv; test on CI target platform only (Linux) |
| Venv size accumulates | Add `make clean-venvs` target; auto-prune venvs for completed projects |

## Blocking

Phase 5 (first real workload). Not needed for Phase 2/3/4 curated fixtures, which have no external dependencies. However, if any Phase 4 spec fixture uses `requests` or similar, this becomes load-bearing earlier.

## Next step

1. Add `VenvManager` class in `workspace.py` or new `venv.py`
2. Add dependency parser for `requirements.txt` (basic: one package per line)
3. Modify `_run_pytest()`, `_run_mypy()`, `_run_ruff()` to accept optional `venv_python` path
4. Add config flag `use_project_venv: bool = False` (default off for Phase 2/3/4)
5. Test on a fixture with a declared dependency (e.g., `requests==2.31.0`)
6. Resolve RFC-006
