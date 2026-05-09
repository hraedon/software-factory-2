---
number: "RFC-006"
title: "Per-project venv isolation for subprocess gates"
severity: medium
status: proposed
kind: design
author: opencode
date: "2026-05-09"
tags: [rfc, gate, stage-5, dep-v1-192]
related: ["RFC-005", "058"]
---

## Summary

v2's mechanical gates (`_run_pytest`, `_run_mypy`, `_run_ruff`, `_run_pytest_collect`) invoke tooling via `sys.executable -m` or `shutil.which("ruff")`. This means they run in the **factory's own Python environment**. When Phase 5 begins building real line-of-business tools, generated code will declare dependencies (e.g., `requests`, `pydantic`, `fastapi`) that are not installed in the factory venv. The gates will fail with `ModuleNotFoundError` even when the implementation and tests are correct.

v1 solved this with per-project venv isolation (BC-192). v2 has no equivalent.

## Scope

This RFC covers:
- Creating a per-project virtual environment before gate execution
- Installing declared dependencies into that venv
- Running subprocess gates inside the isolated environment
- Caching the venv across work-items for the same project to avoid repeated setup

## Deferred decisions

- **Dependency discovery:** Should the factory parse `pyproject.toml` / `requirements.txt` from generated artifacts, or should the spec declare dependencies upfront?
- **Venv location:** Inside `.factory/work/<project_id>/venv/` or adjacent to the factory's own `.venv`?
- **Tool availability:** Should pytest/mypy/ruff be installed into the project venv or remain in the factory venv with PYTHONPATH manipulation?
- **Cleanup policy:** When are project venvs deleted? At project end, or after a TTL?

## Phase needed

Phase 5 (first real workload) or earlier if integration tests begin using generated code with external dependencies.

## Precedent

v1 BC-192: "Per-Project Venv Isolation — Each factory project gets `.factory/venv/` — no more cross-project package collisions from `pip install -e .`."
