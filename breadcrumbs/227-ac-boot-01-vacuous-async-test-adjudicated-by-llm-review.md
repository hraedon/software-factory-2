---
number: "227"
title: "AC-BOOT-01 boot test passes vacuously (async def, no asyncio marker); GR-055 shows it is adjudicated by cross_family_review (LLM), not the RFC-038 boot probe"
severity: high
status: proposed
kind: bug
author: claude-opus (GR-055 review session)
date: "2026-05-31"
tags: [test-efficacy, jury, gate, stage-5, web-service, phase-6, dep-v1-364]
related: ["224", "222", "RFC-038", "RFC-007"]
---

## Symptom

GR-055 (walking-skeleton / AC-BOOT-01 contract) locked 28/50; 22 `cannot_proceed`, of which **17 died at `cross_family_review`** (`review_found_defect`). The cross-family reviewer (Sonnet) pass rate was **6% (1/18)** while the implementer's own `inner_pytest` gate passed **100% (18/18)** on the same artifacts. The 100-vs-6 gap is the whole finding.

Reading all 17 reviewer verdicts, they collapse to **one or two repeated defects**, not 17 independent ones:

- **A — vacuous boot test (17/17).** `test_healthz_returns_200` is declared `async def` with **no `@pytest.mark.asyncio` / `@pytest.mark.anyio` decorator, no `import pytest`, and no `asyncio_mode = "auto"` config anywhere in the bundle.** Verified against the actual emitted test (work item `47a5ee0a…/attempt-0001/artifact.py`): under default pytest the coroutine is collected but never awaited, so the assertions never run and the test passes vacuously. The mechanical `inner_pytest` gate goes green precisely because the test executes nothing.
- **B — missing shared-state init (~6/17).** AC-BOOT-01 requires initializing the declared shared-state layer (SQLite schema, `links` + `hits` tables). Verified against impl `bdf50692…`: no DB, no schema, no tables — only a FastAPI `/healthz`.
- **C — dataclasses not Pydantic (~2/17).** FR-STORE requires Pydantic base models; impl uses stdlib `@dataclass`.

All three reviewer findings are **correct on the merits** (independently verified against source). The cross-family reviewer is not over-strict — it caught a real test-theater defect. The problem is *which gate caught it*.

## Root cause

Two layers:

1. **Upstream generation defect (proximate).** The test_author emits an `async def` boot test without the asyncio marker / `asyncio_mode=auto`, every time — a systematic scaffold bug reproduced across the run, not 17 unlucky drafts. The implementer separately omits the substrate schema init. These are template/contract problems, fixable once upstream, not per-item.

2. **Wrong oracle, by stage placement (structural — the load-bearing one).** The RFC-038 boot probe **does exist and is correct**: `gate/conformance.py::_translate_boot_probe` generates a deterministic, non-worker-authored boot test for AC-BOOT-01 and carries the explicit comment *"AC-BOOT-01 may never pass by model/jury verdict — only by an executed boot probe."* The defect is **where it runs**: `evaluate_conformance` is wired only into the terminal `WORK_ITEM_TYPE_OUTCOME_VERIFICATION` stage, gated behind an integration artifact with a non-empty `assembled_tree` (`gate_process.py:439-489`). `cross_family_review` (per-module, stage ~5) sits **3–4 stages upstream** of that. In GR-055 all 17 boot-AC items died at `cross_family_review` on the **worker-authored** test_suite (the vacuous async test) and never reached integration/outcome_verification — so `evaluate_conformance` was invoked **0 times** (confirmed: 0 `conformance` events in the GR-055 gate log). Net effect: the executed anti-vacuity guarantee is unreachable for any item that dies at per-module review, and a worker-authored test is still the load-bearing artifact at the LLM-review stage — exactly the wrong-oracle pattern BC-224 / RFC-038 warn against, and precisely **dep-v1-364's "tests must fail against the stub" invariant** (a correct boot test must *fail* when the marker/impl is absent; here it *passes* vacuously, and only an LLM reviewer's reasoning — non-deterministic, non-convergent per dep-v1-314 — caught it).

## Impact

High. The boot-AC anti-vacuity guarantee is not holding mechanically. Today it is rescued by an LLM reviewer that happened to reason correctly 17 times; tomorrow (different model, different phrasing, or once the jury out-votes it — see BC-224 quorum-masking) the same vacuous test passes and the skeleton "boots" without being verified. The 56% lock rate is a *symptom* of this, not a review-calibration problem — do **not** loosen `cross_family_review` in response.

Note on RFC-007/RFC-027 (mutation gate): a never-executed test yields kill_rate 0, so mutation testing would also flag this one — but dep-v1-106 already established mutation testing is insufficient for the stub class generally (nothing meaningful to mutate). The reliable fix is execution, not more scoring.

## Proposed fix (directions, for principal decision)

1. **Move the existing RFC-038 boot probe upstream so AC-BOOT-01 is discharged by execution *before* `cross_family_review` is load-bearing for it.** The probe exists (`gate/conformance.py`); it just runs too late (terminal `outcome_verification`). For substrate / AC-BOOT-01 work items, run the deterministic boot probe at the stage these items are actually adjudicated, make it the conformance authority for AC-BOOT-01, and add the must-fail-against-stub guard (dep-v1-364, made blocking). Then `cross_family_review`'s verdict on the boot test becomes advisory, not the gate of record. This matches AC-BOOT-01's stated design.
2. **Fix the test scaffold upstream:** test_author must emit `@pytest.mark.asyncio` or the bundle must carry `asyncio_mode = "auto"`. One-line config change; highest-leverage quick win for the next GR's lock rate, independent of (1).
3. **Tighten the implementer contract** on substrate schema init (Defect B) and Pydantic-vs-dataclass (Defect C).

## Why this isn't the previous fix recurring

Shares tags with BC-224 (`jury`, `test-efficacy`, `web-service`, `phase-6`). BC-224 is the **jury-altitude / quorum-masking** mechanism on web-service ACs; this BC is a **distinct mechanism** — a syntactically-vacuous async test at the boot AC, passing the mechanical gate and being adjudicated by the LLM reviewer because the executed boot probe is staged downstream of where the item dies. The shared invariant they both point to is RFC-038's: *conformance must be executed, not judged.* The invariant is **partially landed** — the boot probe is implemented (`gate/conformance.py`) but only wired at terminal `outcome_verification`, so it does not yet hold for items that die at per-module review. Fix (1) (move/extend the probe so it is the authority for AC-BOOT-01 upstream of `cross_family_review`) is the invariant-establishing fix; fixes (2)/(3) are symptom-level and must not be treated as closing this BC. Per the README fix-recurrence rule, this BC stays open until an executed probe — not an LLM verdict — is what discharges AC-BOOT-01 at the stage these items are gated.

## Progress (2026-05-31) — fixes implemented + validated

The plan `plans/2026-05-31-ac-boot-01-vacuity-gap.md` was implemented (WS-1
asyncio config + must-fail-against-stub; WS-2 `evaluate_module_boot_probe` at the
implementation gate; WS-3 review advisory for executable ACs) and validated
across GR-056/057:

- **WS-1 confirmed:** 0 `review_found_defect` in both runs (vs this BC's 17) —
  the vacuous-async-test class is eliminated.
- **WS-2 confirmed** by controlled experiment on `evaluate_module_boot_probe`:
  FastAPI+`/healthz` → PASS, no-app stub → FAIL (anti-vacuity holds), `/docs`
  fallback → PASS. The executed boot probe runs upstream of review and discharges
  AC-BOOT-01 by execution, not LLM verdict.
- Fixed a GR-056 blocker en route: the conformance gate venv (`uv venv`, no pip)
  now installs requirements via `uv pip` (see launch log).

Still open: the fixes are **uncommitted** in the sf2 working tree; follow-ups
BC-229 (telemetry unknown-gate) and BC-230 (launcher cleanup exit-1). This BC
stays open until the fixes are committed and a 055-scale clean comparison
confirms the lock-rate recovery holds at scale.
