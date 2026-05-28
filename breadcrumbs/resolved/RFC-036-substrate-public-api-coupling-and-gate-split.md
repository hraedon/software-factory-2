---
number: "RFC-036"
title: "Eliminate regista private-API imports; split gate.py into a gate/ package"
severity: medium
status: implemented
kind: design
author: claude
date: "2026-05-18"
tags: [coupling, refactor, gate, regista-public-api]
related: ["RFC-011"]
---

# RFC-036 — Two adjacent refactors that block each other if either is done alone

## Motivation

Two findings from the most recent adversarial review have the same shape: load-bearing code that touches surfaces it shouldn't.

### Regista private-API coupling

`src/factory/pipeline_docs.py:6` (and two siblings flagged by `tests/test_substrate_private_api_coupling.py`) imports from `regista._workflow_compose`. The "test" asserts those imports exist — i.e., it pins the coupling rather than testing behavior. Regista is about to evolve (a second consumer is being scaffolded; regista's `debate/001` Option-B work, RFC-001 on event_id uniqueness, etc.). Every private-API touchpoint is a hidden break.

### `gate.py` god module

`src/factory/gate.py` (≈1,387 lines as of GR-038) mixes:

- Deterministic gates (syntax, stub, AC binding)
- Subprocess gates (mypy, pytest, ruff)
- Model-mediated gates (review, jury)
- The integration assembler (which is the BC-188 RCE site)

With Phase 3 expansion of channel/role combinations, every gate change touches the file. RFC-011 separated subprocess invocation; this RFC separates gate kinds.

## Proposal

### Part 1 — Regista public API surface

Open a regista issue (or RFC) requesting a public `regista.workflow_compose` API covering what `pipeline_docs.py` and friends need today. Until that lands, ring-fence the private imports in a single `src/factory/_substrate_private.py` module whose tests *also* run against the actual regista version pinned in `pyproject.toml`, so a regista upgrade breaks the test loudly rather than the runner subtly.

### Part 2 — `gate.py` → `gate/` package

Split into:

- `gate/__init__.py` — re-exports the small public surface (`evaluate_gate`, `GateResult`)
- `gate/deterministic.py` — syntax, stub, AC binding
- `gate/subprocess.py` — mypy, pytest, ruff (already partly factored by RFC-011's subprocess wrapper)
- `gate/model.py` — review, jury
- `gate/integration.py` — the assembled-tree path; **inherits BC-188's sandboxing fix as part of this split**
- `gate/_shared.py` — common helpers

## Why bundled

If Part 1 lands without Part 2, any regista API change still ripples through a god module. If Part 2 lands without Part 1, the split modules each carry the private-import sin and the surface for regista breakage gets wider, not narrower.

## Acceptance criteria

1. `grep -r "from regista\._" src/factory/` returns matches only under `src/factory/_substrate_private.py`.
2. No file in `src/factory/gate/` exceeds 400 lines.
3. BC-188's sandboxing fix lands as part of `gate/integration.py`.
4. Test coverage for each split module ≥ what `gate.py` had pre-split.

## Decision

_(pending)_
