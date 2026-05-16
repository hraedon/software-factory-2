---
number: "RFC-028"
title: "Per-role capability map — collapse 5-point registration into single declaration"
severity: medium
status: proposed
kind: design
author: opencode
date: "2026-05-15"
tags: [runner, gate, pre-gate, telemetry, artifact, rfc]
related: ["170", "CLASS-021", "155"]
---

## Problem

Adding a role with a non-default artifact format requires touching at least 5 separate locations:

1. `subprocess_channel.py` — `_artifact_extension_for_role()` (artifact format)
2. `runner.py` — `_run_pre_gate()` (pre-gate dispatch)
3. `runner.py` — `_inner_gate_label()` (telemetry gate-name label)
4. `telemetry.py` — `DETERMINISTIC_GATES` (gate-name registration)
5. `gate_process.py` — outer gate dispatch (`process_gate_item()`)

BC-170 demonstrated what happens when one of these registrations is missed: the integrator role fell through to the Python-centric pre-gate path, ruff silently corrupted a JSON artifact, and the failure surfaced only at the outer gate's `json.loads()` call. The test suite had no coverage for the new code paths (CLASS-014 instance).

This is the same class of problem as BC-155 (integrator/outcome_verifier excluded from `_INNER_GATE_ROLES`) and CLASS-012 (string constant gravity). Each new role is a latent registration minefield.

## Proposal

Introduce a `RoleCapabilities` dataclass that declares, for each role, everything the pipeline needs:

```python
@dataclass(frozen=True)
class RoleCapabilities:
    artifact_extension: str          # ".py", ".pyi", ".json"
    pre_gate_fn: Callable            # pre_gate_integrator, pre_gate_implementation, etc.
    inner_gate_label: str | None     # GATE_NAME_INNER_JSON_SHAPE, etc.
    outer_gate_fn: Callable          # evaluate_integration, evaluate_implementation, etc.
    deterministic_gate_names: set[str]  # for telemetry registration
```

A single `ROLE_CAPABILITIES: dict[str, RoleCapabilities]` replaces the scattered if/elif chains. Adding a new role becomes one dict entry instead of 5 file edits.

Derived lookups:
- `_artifact_extension_for_role(role)` → `ROLE_CAPABILITIES[role].artifact_extension`
- `_run_pre_gate(role, ...)` → `ROLE_CAPABILITIES[role].pre_gate_fn(...)`
- `_inner_gate_label(result, role)` → `ROLE_CAPABILITIES[role].inner_gate_label`
- `DETERMINISTIC_GATES` → union of all `deterministic_gate_names` across roles

The outer gate dispatch (`gate_process.py`) is harder to collapse because it has dependency-resolution logic per work-item type (interface_ref, test_suite_ref, etc.), but it can at least validate that the work-item type has a registered `outer_gate_fn`.

## Scope

This is a refactoring RFC. It changes no behavior — all current roles get the same dispatch they have today. The value is in making the next role addition a one-point change.

## Phase needed

Phase 5 exit or Phase 6. Not blocking — the current dispatch works for the 7 defined roles. But before adding coherence_reviewer or any future role, this map should exist to prevent a repeat of BC-170.

## Risks

- The outer gate's dependency-resolution logic (per work-item-type if/elif in `gate_process.py`) doesn't map cleanly to a simple callable — each branch resolves different refs before calling the gate function. A partial application (currying the resolved deps) could work, but adds indirection. The RFC should start with the 4 simple registrations and leave the outer gate as a follow-up.
- Over-abstracting role capabilities too early could make the common case (Python roles with ruff+mypy+pytest) harder to reason about. The map should be additive — Python roles can share a default `RoleCapabilities` instance.
