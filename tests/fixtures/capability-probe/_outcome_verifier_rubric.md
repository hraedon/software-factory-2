# Capability-Probe Answer Key — outcome_verifier

**Do not show this file to models under evaluation.**

## Planted defects in the assembly

| ID | Defect | AC violation | Expected detection |
|----|--------|------------|------------------|
| D1 | `consume` returns `bool` instead of `int` (tokens remaining per AC-02) | AC-02 | verdict=fail, routing_hint=implementation |
| D2 | AC-03 says return `None` on insufficient; AC-04 says raise `RateLimitExceeded` on empty. Implementation only raises, never returns `None`. | AC-03 | verdict=fail, routing_hint=implementation |
| D3 | Calls `clock.monotonic_seconds()` which does not exist; only `monotonic_ns` is available. | AC-06 | verdict=fail, routing_hint=implementation |
| D4 | No clamp for negative `elapsed`; no guard for `refill_per_second <= 0`. | AC-05 | verdict=fail, routing_hint=implementation |
| D5 | No validation for `tokens <= 0` or `tokens > capacity`. | AC-01 / AC-02 | verdict=fail, routing_hint=implementation |
| D6 | Integration tests are weak — they don't catch any of the above. | N/A (test quality) | verdict=fail, routing_hint=test_suite (optional; acceptable if routed to implementation instead) |

## Scoring rubric

For each model:

| Criterion | Points | Description |
|-----------|--------|-------------|
| JSON valid | 1 | Output is exactly one fenced JSON block with all required fields |
| Verdict correct | 2 | `verdict` is `"fail"` (the assembly is objectively broken) |
| Rationale quality | 1 | Rationale names at least one specific AC violation |
| Routing hint present | 1 | `routing_hint` is non-null when `verdict` is `"fail"` |
| Routing hint accurate | 2 | `routing_hint.work_item_type` is `"implementation"` (all defects are in the impl module) |
| D1 detected | 1 | Rationale or hint references return-type mismatch |
| D2 detected | 1 | Rationale or hint references missing `None` return path |
| D3 detected | 1 | Rationale or hint references missing `clock.monotonic_seconds` |
| D4 detected | 1 | Rationale or hint references missing edge-case guards |
| D5 detected | 1 | Rationale or hint references missing input validation |

**Maximum score: 12**

## Pass thresholds

- **Probe pass**: score >= 8/12 AND verdict == "fail" AND routing_hint accurate
- **Probe partial**: score >= 5/12 AND verdict == "fail" but routing_hint missing or wrong
- **Probe fail**: score < 5/12 OR verdict != "fail"

## Methodology

- Single-attempt, no inner gate (outcome_verifier is a model-mediated gate).
- Use the production prompt template (`src/factory/prompts/outcome_verifier.md`).
- Provide the flawed assembly + weak integration tests from the fixture directory.
- Record raw output and score manually against this rubric.
