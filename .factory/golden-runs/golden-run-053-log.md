# GR-053 — Archetype-Aware Contract Plumbing (web-service altitude fix)

**Date:** 2026-05-30
**Config:** golden-run-053-config.yaml
**Fixture:** url-shortener (spec.yaml, decomposed via Phase C model — MiMo-V2.5-Pro)
**Channels:** opencode (kimi-k2p6-turbo) for arch/test/impl/integrator/outcome;
claude-code (sonnet) for cross_family_reviewer; jury = K2 + GLM-5.1 + MiMo
(Sonnet dropped from jury to cap Sonnet budget; kept only as reviewer)
**Executor:** agent_golden_run.py (Phase C, `--spec-yaml` + decomposer)
**Workflow version:** 5 (full pipeline)

## Purpose

First run after the archetype-contract plumbing change (activate the dead
`Archetype.prompt_addendum` path; carry per-module archetype to the prompts;
make the web-service contract an ASGI route table instead of a pure-function
`.pyi`). Validate that the interface/test/implementer stages now produce an
HTTP deliverable instead of GR-052's pure functions, and that
`outcome_verification` can go non-zero **without a framework name entering the
contract**.

## Result summary

| Metric | Value | Pass? |
|---|---|---|
| Interface specs | 5 locked (5/5) | ✅ all HTTP-shaped |
| Test suites | 3 locked, 2 cannot_proceed | partial |
| Implementations | 1 locked, 2 cannot_proceed | partial |
| Review | 1 locked | — |
| Jury | 1 cannot_proceed | — |
| Integration | none reached | — |
| Outcome verification | **none reached** | ❌ DAG did not complete |
| Full DAG reached? | **NO** (stalled at test_suite/implementation) | ❌ |

**Overall: INCONCLUSIVE on the headline metric — but the contract fix is
validated, and the stall has a single, verified, fixed root cause.**

## What the fix achieved (validated by artifacts)

The altitude collapse from GR-052 is **gone at the source**:

- **Interface specs: all 5 locked, and HTTP-shaped.** The locked `stats_reader`
  contract is `app` (ASGI application) + a route table
  (`GET /links/{slug}/stats -> 200 LinkStatsResponse`) + typed response models —
  not a `def resolve_link(...) -> Redirect` pure function. Stage 1 produced HTTP
  contracts that *passed* the mechanical + review + jury gates.
- **Test author writes async ASGI tests.** The test suites use
  `httpx.AsyncClient` over `ASGITransport(app=app)` and assert on HTTP **status
  codes** (`assert response.status_code == 201`) — exactly the contract's intent.
- **Implementer writes a real web framework** (FastAPI/httpx/pydantic saturate
  the artifacts).
- **`archetype=web-service` reached every module** through the real pipeline
  (regista accepted the new custom field; no `CUSTOM_FIELD_VIOLATION`).

This is a categorical change from GR-052 (which shipped non-HTTP pure functions
that the conformance gate correctly rejected at 0%).

## Why the DAG stalled — root cause (verified by reproduction)

Two of five test suites and two of three implementations escalated to
`cannot_proceed` on the **inner `test_suite_collect` gate**, with:

```
ImportError: cannot import name 'app' from 'interface'
```

The interface architect declared the entry point as an **annotation-only**
binding (`app: Callable[..., Awaitable[None]]` / `app: object`). In a `.pyi`
this is idiomatic, but the gate copies the stub to `interface.py` and imports
it; an annotation without assignment creates **no importable name**. The test
author correctly wrote `from interface import app`, which then fails at
collection. Cascade: test_suite cannot_proceed → implementation/integration
starved → outcome never reached.

Reproduced locally: collecting the exact GR-053 test against the locked stub
fails with the ImportError; changing the stub's `app:` annotation to an
assigned `app = ...` makes the same suite collect cleanly (4 tests). Confirmed
this was **not** an async-runner or missing-dependency problem (httpx/anyio were
present; the failure was purely the unbound name).

## Fix applied (this session, verified)

1. **Web-service contract: `app` must be an importable binding.**
   `catalog/web-service/prompt_addendum.md` now requires the interface stub to
   write `app = ...` (assigned Ellipsis placeholder), not an annotation-only
   `app: SomeType`. The implementer replaces it with the real app.
2. **Gate can run async tests.** Added `pytest-asyncio` to the gate venv
   (`_GATE_TOOLS`) and `-o asyncio_mode=auto` to the inner-gate pytest
   collect/run (`gate/_subprocess.py`). The web-service addendum tells the test
   author to write plain `async def` tests (no `@pytest.mark.asyncio`/
   `anyio_backend`). Verified end-to-end: a plain `async def` httpx test against
   a real ASGI app collects against the `app = ...` stub and **passes** at run.

Both fixes are framework-neutral (httpx + asyncio; no framework named in any
graded artifact).

## Honest verdict

The fix **moved the failure forward**, decisively: from GR-052's *"silently
ships non-HTTP stubs the gate rejects"* (0%, right reason) to *"produces correct
HTTP contracts + tests, blocked by an annotation-vs-binding stub detail."* The
altitude/contract problem the change targeted is solved and visible in locked
artifacts. But `outcome_verification` never ran, so **end-to-end success is
unproven** — this run does not claim it.

The remaining blocker was narrow, fully diagnosed, and fixed + verified. Next
concrete step: **GR-054** re-runs the same Phase C url-shortener with the
binding + async-runner fixes; success criterion unchanged — outcome_verification
non-zero with no framework name in the contract.

## Telemetry note

`verify_passed: False`, one `unknown` gate name, one `orphan_submit` — integrity
flags consistent with the mid-DAG cascade (items abandoned at cannot_proceed),
not a measurement defect. Re-check on GR-054.

## Artifacts

- Workspace: `/tmp/sf2-golden-053/` (preserved, `--no-cleanup`)
- Logs: `.factory/logs/golden-run-053-config/`
