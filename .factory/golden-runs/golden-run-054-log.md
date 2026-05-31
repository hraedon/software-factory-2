# GR-054 — Web-service contract validated through implementation; new frontier = integration composition

**Date:** 2026-05-30
**Config:** golden-run-054-config.yaml (same as GR-053: GLM-5.1 jury seat, Sonnet reviewer)
**Fixture:** url-shortener (spec.yaml, Phase C model decomposition — MiMo-V2.5-Pro)
**Workflow version:** 5 (full pipeline)

## Purpose

Re-run GR-053 with the two fixes for its verified stub-binding blocker:
(1) web-service contract requires `app` to be an importable binding (`app = ...`),
(2) gate venv gets `pytest-asyncio` + `asyncio_mode=auto` so async ASGI tests run.

## Result summary

| Stage | GR-053 | GR-054 | Read |
|---|---|---|---|
| interface_spec | 5 locked | **5 locked** | HTTP-shaped contracts |
| test_suite | 3 locked, 2 dead | **5 locked** | ✅ collection blocker gone |
| implementation | 1 locked, 2 dead | **11 locked, 0 dead** | ✅ async HTTP tests run + pass vs real FastAPI |
| review | 1 locked | 5 locked, 6 dead | churn |
| jury | 1 dead | 3 locked, 2 dead | quorum mostly met |
| integration | none | **3 cannot_proceed, 0 locked** | ❌ new blocker |
| outcome_verification | none | **none** | ❌ DAG still incomplete |
| Telemetry verify | False (unknown gate, orphan) | **True, 0/0/0** | ✅ clean |

**Overall: the archetype-contract fix is VALIDATED through implementation. The
DAG still does not reach outcome_verification — it now stalls one stage deeper,
at integration (multi-module ASGI composition).**

## What is now proven

Stages 1–3 work for the web-service archetype:
- 5/5 interface specs lock as ASGI `app` + route tables (not pure functions).
- 5/5 test suites lock — async `httpx.AsyncClient` tests collect against the
  `app = ...` stub and run.
- 11/11 implementations lock — real FastAPI apps (≈115 lines each) that **pass
  their own async HTTP tests** at the implementation gate.
- Telemetry integrity clean (verify_passed True; 0 unknown / orphan / unmatched).

This is the categorical advance the change targeted: GR-052 shipped non-HTTP
stubs (0% for the right reason); GR-054 ships working HTTP modules that satisfy
HTTP ACs at the module level.

## New blocker — integration composition (genuine, not a harness bug)

The 3 integration items escalate to cannot_proceed on `integration_mypy` /
`integration_pytest`. The integrator **does** follow the web-service convention —
it emits a top-level `app.py` with `entry_point: app.app` — but composes by
mounting each module's standalone app:

```python
app = FastAPI()
@app.get("/healthz")
async def healthz() -> HealthzResponse: return await get_healthz()
app.mount("/", link_resolver_app)
```

Two real problems:
1. **Each module exposes a standalone `app`**, so composition = merging N FastAPI
   apps. Mounting them all at `/` collides / shadows; routes don't land at the
   AC paths cleanly. The clean composition primitive is *routers* (or a shared
   app modules register onto), not standalone apps — but "router" is
   framework-specific, in tension with the framework-neutral contract.
2. **Each integration item assembles only one jury lineage's closure**
   (here link_resolver + link_store), so a single assembled app cannot satisfy
   cross-module ACs (POST /links lives in link_creator). For pure-function
   modules (GR-052) this was trivial; for HTTP apps it is not.

This difficulty is **new and introduced by the correct HTTP contract** — exactly
the next frontier once the altitude fix lands.

## Decision required (not a quick patch)

How should independently-built HTTP modules compose into one service? Open
options (architectural, deferred to the principal):
- **A. Modules expose composable route surfaces** (e.g. an `APIRouter`/route list
  designed for inclusion), and the integrator/skeleton owns the single `app` that
  includes them all. Cleanest composition; costs some framework neutrality and
  some per-module standalone-testability.
- **B. Walking-skeleton**: a substrate module owns the single `app`; feature
  modules register their routes onto it. Matches the decomposer's existing
  walking-skeleton language.
- **C. Keep per-module apps; give the integrator a real merge strategy** (extract
  and re-register routes onto one app). Preserves the current contract; most
  fragile.

## Trajectory

GR-052 (stage-1 altitude) → GR-053 (stage-2 stub binding) → GR-054 (stage-7
integration composition). Each blocker is deeper in the DAG and more legitimate
than the last — convergence, not thrashing.

## Artifacts

- Workspace: `/tmp/sf2-golden-054/` (preserved, `--no-cleanup`)
- Logs: `.factory/logs/golden-run-054-config/`
