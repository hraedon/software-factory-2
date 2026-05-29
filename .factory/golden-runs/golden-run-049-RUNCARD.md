# GR-049 Run Card — ephemeral execution gate vs. EXISTING atomic url-shortener (confirm stubs fail)

**Status:** blocked on RFC-038 MVP build (the gate does not exist yet)
**Purpose:** Convert GR-048's hand-read finding into a mechanical, repeatable conformance signal — *before* changing the decomposer. This is the RFC-038 falsification instrument applied to the current pipeline.
**References:** RFC-038 (the gate), RFC-039 (the hypothesis this instrument will later test), BC-224, BC-222, GR-048.

---

## What this run is (and isn't)

This is **not** a full pipeline run. It is: build the minimal ephemeral execution gate, then point it at the **existing, atomic-decomposed** url-shortener output and observe that it fails deterministically. **Change nothing in the pipeline or decomposer.** The whole value is that the diagnosis is confirmed by execution on unchanged inputs.

GR-050 (separate, later) will run deliverable-decomposed output (RFC-039) through the *same* gate. The gate is the constant; the decomposition is the variable. Do not conflate the two runs.

## Prerequisite — build the RFC-038 MVP gate first

A thin module that, given the assembled module artifacts of a web-service workload:

1. Assembles the modules into one app and starts it in **one ephemeral container** (no v1 fingerprint/cache/registry — start → health-probe-until-ready → run → tear down → discard).
2. Runs an acceptance suite **deterministically translated** from the spec's AC scenarios (they are already black-box HTTP: `POST /links {"url":123}` → assert status 422, etc.). Seed fixtures from the AC text ("Given 25 links in the database" → seed 25 rows).
3. Enforces the **must-fail-against-stub guard (dep-v1-364)** as a blocking pre-check: the generated suite must FAIL against the unimplemented skeleton, or the suite is rejected as not testing the contract.

Keep the container dumb and ephemeral. If effort drifts into container plumbing, that is the tell it's avoiding the load-bearing part (the translation). Host-execution fallback is acceptable for the MVP.

## Input

The atomic-decomposed url-shortener module artifacts. Either reuse the preserved GR-048 workspace if still present (`/tmp/sf2-golden-048`, 107 MB — check first; it is in `/tmp` and may be gone), or re-populate + run a fresh atomic pipeline exactly as GR-047/048 did (MiMo decomposer, K2 workers) to regenerate a clean set.

## Expected result (the hypothesis for THIS run)

The gate fails the stub modules deterministically:

- **Boot probe fails** — no module imports FastAPI; there is no HTTP server to start. (This alone is the headline.)
- **AC scenarios fail** — no `POST /links` returning 422 (FR-05); `GET /links` returns fabricated `example.com/00..24` instead of DB rows (FR-04).

## Success / failure criteria

- **Success:** the gate catches what review + 2/3 of the jury missed in GR-048 — i.e. it blocks the stub modules on AC-conformance grounds, deterministically and repeatably. The diagnosis (BC-224) is now mechanically confirmed.
- **Gate is broken (investigate, do not proceed to GR-050):** if the gate *passes* the stubs. That means the acceptance suite is asserting the wrong thing (e.g. calling `validate_url()` and checking the object instead of issuing an HTTP request) — the exact GR-048 blind spot reimported into the harness. The dep-v1-364 must-fail-against-stub guard should have caught this; if it didn't, the guard is the bug.

## Log requirements

Record: whether the boot probe ran a real server; per-AC pass/fail from the executed suite; and an explicit statement of whether the must-fail-against-stub guard fired during suite generation. Then write `golden-run-049-log.md` and reconcile this runcard's `Status:` (BC-223).
