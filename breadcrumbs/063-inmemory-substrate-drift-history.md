---
number: "063"
title: "InMemorySubstrate drift history — integration test surface is 10x smaller than unit test surface"
severity: medium
status: proposed
kind: design
author: adversarial-reviewer
date: "2026-05-08"
tags: [dep-substrate-*, runner, gate]
related: ["018", "030", "035", "036"]
---

## Summary

~270 unit tests use `InMemorySubstrate`. ~10 integration tests hit real Postgres Substrate. The in-memory backend has a documented history of behavioral divergence (BC-040, BC-048, BC-050, BC-051, BC-054 on the substrate side; BC-018, BC-030, BC-035, BC-036 on the factory side).

Golden-run-002 found two bugs that all 200+ unit tests missed:
- Cross-work-item module resolution (tests used same-directory import patterns)
- Escalation routing no-op (tests didn't exercise the full state machine with real Substrate)

## Risk

The surface area for further behavioral divergence still exists. Any difference between `InMemorySubstrate` and `Substrate` for methods SF2 calls (claim lifecycle, transition semantics, event ordering, custom_field validation) will produce tests that pass but production code that fails.

## Mitigations already in place

- `test_substrate_private_api_coupling.py` — canary test for API churn
- `test_phase2_workflow_roundtrip.py` — full workflow validation against real Substrate
- `test_pipeline_integration_real.py` — end-to-end on real Substrate

## Proposed

1. Add a `make integration` target that runs all `@pytest.mark.integration` tests against real Postgres
2. Add at least one integration test matching each golden run shape (pure-interface, error-taxonomy, ADT-validation, adversarial)
3. Consider a `make replay` target that replays golden run artifacts through real Substrate + real gates
