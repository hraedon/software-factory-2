# Breadcrumbs

Defects, design questions, and improvements for software-factory-2. One file per item, numbered for reference. Numbers do not imply priority — see `severity` in each file's frontmatter.

Schema follows substrate's breadcrumbs convention; see `/projects/substrate/breadcrumbs/README.md` for the canonical reference.

## Schema

```yaml
---
number: "001"
title: Short descriptive title
severity: critical | high | medium | low
status: proposed | in_progress | implemented | obsolete
kind: bug | design | improvement
author: who-raised-it
date: "YYYY-MM-DD"
tags: [topic, stage-N, dep-substrate-NNN]
related: ["002", "003"]
---
```

## Severity

- **critical** — blocks correct operation; v2 cannot be trusted for stated guarantees
- **high** — load-bearing spec property unfulfilled; silent-correctness risk
- **medium** — defect with workaround or limited blast radius
- **low** — edge case, polish, or minor ergonomics

## Tags

Reusable tags:
- `stage-0` through `stage-10` — pipeline stage from spec §4
- `dep-substrate-NNN` — blocks on substrate breadcrumb NNN
- `channel-claude`, `channel-k2`, `channel-glm`, `channel-deepseek`, `channel-gemini`, `channel-opencode`
- `tier-a`, `tier-b`, `tier-c` — capability tier (spec §5)
- `runner`, `telemetry`, `gate`, `jury`, `race`, `failure-routing`

## Open

(No open breadcrumbs.)

## Resolved

| # | Title | Severity | Resolution |
|---|---|---|---|
| 028 | Dead MockSubstrate file — tests/_mock_substrate.py | low | Deleted after InMemorySubstrate migration confirmed stable |
| 027 | Wave 5 — cross-stage escalation routing | high | Escalation in router with attempt_threshold; CANNOT_PROCEED_SEAM kind |
| 026 | Scheduler idempotency — global has_link_type query skips unrelated sources | medium | Per-source custom_fields ref check in _ensure_downstream_item |
| 025 | evaluate_implementation missing subprocess gates | high | Added import/mypy/pytest/ruff gates with correct DiagnosticKind |
| 021 | Non-cannot_proceed channel failures produce no substrate event for telemetry | high | Added sub.append_event(transition="channel_fail") in _handle_invoke_failure; updated MockSubstrate + tests |
| 024 | _resume_and_submit hardcodes role to interface_architect | high | Parameterized role_name in runner.py; added test |
| 023 | Structural semantics gate rejected module-level AC docstrings | high | Extended _check_structural_semantics to honor module docstrings |
| 022 | Integration tests access substrate private API — _mgr._dsn and _project | medium | Introduced factory_config fixture using public substrate.project |
| 020 | Config YAML loading untested — from_yaml, from_yaml_or_default | low | Added 6 tests in test_config.py |
| 019 | Channel failure modes untested — timeout, non-zero exit, extraction failure | high | Added 5 tests in test_channel_failures.py |
| 018 | MockSubstrate diverges from real substrate — workflow_version filtering, event payload | medium | Fixed query_work_items filtering; removed state_map fallback; verified read_events signature |
| 017 | Router is dead code — route() never called by gate_process | medium | Wired route() into process_gate_item; diagnostics via routing table |
| 016 | AC reference check uses substring search — false positives likely | medium | Removed _check_ac_references; module docstring support added |
| 015 | Integration test private substrate API coupling | medium | Public API workaround via factory_config fixture; substrate-level request for Substrate.dsn remains open |
| 014 | Resume path (_resume_and_submit) untested at integration level | high | Added 3 tests in test_runner_resume.py; fixed hardcoded role |
| 008 | Fixture AC-15 mislabel in 04-verify_event_errors.md | high | Fixed AC-15 text to describe verify_event rejection behavior |
| 009 | context_hash → artifact non-determinism; replay tests must assert structure | high | Added structural_signature() + structurally_equivalent_pyi() in gate.py with 10 tests |
| 010 | populate_work_items.py --reset does not clean workspace | high | Added --workspace-root argument; shutil.rmtree on --reset |
| 011 | Test gap — claim transition not asserted in worker loop tests | high | Added 3 tests (MockSubstrate + live) asserting claim transition event and in_progress state |
| 012 | Context derivation tests should exercise both spec_file paths | high | Added 5 tests covering work-item priority, factory fallback, empty, preservation, hash differentiation |
| 013 | Gate is syntactic-only — semantic gating strategy (option c: hybrid stopgaps) | high | Added structural-semantic checks: function count, return types, parameter presence, AC-to-function binding |
| 007 | Integration tests are stubs | medium | Replaced gate_process stub with real process_gate_item tests; Kimi fixed smoke test; added MockSubstrate pipeline tests |
| 006 | MockSubstrate needed for CI-portable tests | medium | Built MockSubstrate test double + 5 CI-portable pipeline tests |
| 005 | Spec content resolution for context derivation | high | Added spec_file config + loader; Phase 1 uses inline, Phase 2 needs section extraction |
| 004 | cannot_proceed routing has no workflow path | high | Added cannot_proceed terminal state + transition to both YAMLs; runner bypasses gate |
| 002 | Runner skeleton complexity risk | medium | Implemented: 7-module decomposition built per BC-002 spec |
| 003 | Runner idempotency on restart | high | Implemented: §9.12 spec amendment applied, workspace + tests done |
| 001 | Dead error codes: defined but never raised | low | Moved to substrate/breadcrumbs/026 — not a factory issue |
