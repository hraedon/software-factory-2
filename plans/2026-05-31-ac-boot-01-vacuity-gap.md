# Plan: close the AC-BOOT-01 vacuity gap (GR-055 → GR-056)

> **Status:** proposed, dispatch-ready. Scoped to the walking-skeleton / AC-BOOT-01
> path (one variable at a time).
> **Lineage:** BC-227 (the defect), BC-224 (jury/review-as-oracle root cause),
> RFC-038 (verification-driven conformance gate / boot probe — *partially landed*),
> RFC-039 (deliverable decomposition / walking skeleton), RFC-030 (promote to an
> invariant, no per-symptom exceptions), dep-v1-364 (must-fail-against-stub),
> dep-v1-314 (non-completion is the primary risk).
> **Author:** opus review session, 2026-05-31.

## Core diagnosis (verified against code + GR-055 logs)

The RFC-038 boot probe **already exists and is correct** — `gate/conformance.py::_translate_boot_probe`
generates a deterministic, non-worker-authored boot test for AC-BOOT-01, with the
explicit invariant *"AC-BOOT-01 may never pass by model/jury verdict — only by an
executed boot probe."* The defect is **stage placement**: `evaluate_conformance` is
wired only into the terminal `WORK_ITEM_TYPE_OUTCOME_VERIFICATION` step, gated behind
an integration artifact with a non-empty `assembled_tree` (`gate_process.py:439-489`).
`cross_family_review` (per-module, stage ~5) sits 3–4 stages upstream. In GR-055 all
17 boot-AC items died at `cross_family_review` on the **worker-authored** vacuous async
test and never reached integration — so `evaluate_conformance` ran **0 times**
(confirmed: 0 `conformance` events in the GR-055 gate log).

Fix = move the executed authority upstream + make the worker test un-vacuous-able.
**Reuse the probe; do not rebuild it.**

## Guardrails (non-negotiable)

- Primary failure mode is non-completion (dep-v1-314 died `in_progress`). Keep the
  probe **ephemeral and dumb**: start → health-probe → run → discard. No fingerprinting,
  image cache, or v1 apparatus.
- AC-BOOT-01 anti-vacuity is an **invariant** (RFC-030). No category bypasses.
- **Do not** widen executed-conformance beyond AC-BOOT-01 in this batch. Generalizing
  to all ACs is RFC-039-dependent and out of scope here.

## Locked decisions (principal, 2026-05-31)

1. **Executable-vs-judgment AC boundary** = the spec's existing `acceptance_criteria`
   section (executed) vs `untestable_items` / `nfr` (judgment). RFC-038 measured ~100%
   of `acceptance_criteria` as mechanically translatable, so the line is essentially free.
2. **No LLM-review→implementer repair loop now.** WS-2/3 route *execution* failures back
   via the existing `create_upstream_revision` rail. Revisit a bounded, guard-railed LLM
   repair loop only if a post-WS-3 GR shows genuine *logic* defects (not scaffold/contract)
   dying at review.

---

## WS-1 — Kill the vacuous async test (ship first, independent, low-risk)

**Goal:** a worker-authored async test can never pass without executing.

- **(a)** Inject `[tool.pytest.ini_options] asyncio_mode = "auto"` into the generated
  project's config from the **harness**, not the test_author prompt (model-authored
  config is the GR-048 blind spot). Belt-and-suspenders: test_author also emits
  `@pytest.mark.asyncio`.
- **(b)** Must-fail-against-stub guard (dep-v1-364, made **blocking**): in the inner test
  gate, run the AC/boot test against the unimplemented skeleton; any test that *passes*
  before implementation exists is rejected with `diagnostic_kind = vacuous_test`.

**Files:** `src/factory/prompts/test_author.md`, `src/factory/inner_gate.py`,
generated-project config templating.
**Done when:** a deliberately marker-less async test is caught deterministically (not by
an LLM); a correct one passes.

## WS-2 — Move the executed boot probe upstream (structural)

**Goal:** AC-BOOT-01 discharged by execution at the stage substrate items are gated.

- Invoke the **existing** `evaluate_conformance` / `_translate_boot_probe` for
  substrate / AC-BOOT-01 work items at the per-module review/integration point where they
  currently die; make its result the **gate of record** for AC-BOOT-01.
- The substrate module (app factory + DB schema) is independently bootable by design
  (`plans/2026-05-30-substrate-boot-ac-invariant.md`), so the probe runs on it alone.
  Relax the `assembled_tree`-only precondition for this case.

**Files:** `src/factory/gate_process.py` (dispatch), `src/factory/gate/conformance.py`
(single-substrate-module invocation), `workflows/full_pipeline.yaml`.
**Done when:** a GR-055-equivalent run shows `evaluate_conformance` invoked once per
substrate/boot item (currently 0); vacuous-boot items are blocked by the executed probe,
not `cross_family_review`.

## WS-3 — Demote `cross_family_review` from conformance authority

**Goal:** review stays for design/security/readability; "meets the executable AC" is
decided by execution; failures feed back via the existing `create_upstream_revision` rail.

- For executable ACs, a `cross_family_review` "defect" becomes **advisory** (annotates,
  doesn't terminally block). Conformance-gate failures route back to the responsible
  upstream item with the concrete failing scenario.

**Files:** `src/factory/gate/review.py` (or `evaluate_review`), the
`Route`/`create_upstream_revision` wiring, gate/role config in the workflow.
**Done when:** a conformance failure produces an upstream revision carrying the failing
scenario; an LLM-review opinion on an executable AC no longer terminally blocks.
**Couples to WS-2 — dispatch together.**

## WS-4 — Validate on a real run (gating; the falsification instrument)

- Re-run the walking-skeleton workload after WS-1 (alone), then again after WS-2+3.
- **Exit criteria:** conformance invoked for all substrate/boot items; asyncio vacuity
  defect impossible or deterministically caught; first-gate-eval pass rate **≥60%**
  (failed at 57% in GR-055); lock rate recovers if underlying impls are sound; no new
  `unknown_gate`.

---

## Sequencing

```
WS-1 ──────────────► GR-056a (measure lock-rate recovery alone)
                          │
WS-2 ──┬──► WS-3 ─────────┴──► GR-056b (confirm executed probe is the authority)
       └ reuse existing probe; keep ephemeral
```

WS-1 is dispatchable now, in isolation — no architectural decision required, and likely
recovers most of the lost lock rate on its own. WS-2 and WS-3 are coupled and dispatched
together once WS-1 is in.

---

## Launch log

### GR-056 — 2026-05-31 (decision recorded per principal request)

**Decision: Form A — Phase C model decomposition** (chosen over Form B, the
pre-decomposed `wi_*.md` fixtures). Rationale: GR-050–055 ran Phase C deliverable
decomposition (substrate boot-AC); to validate the AC-BOOT-01 vacuity fixes
(WS-1/2/3) against the *same* pipeline path as 055, decompose the url-shortener
`spec.yaml` with the model decomposer rather than feed pre-decomposed work items.

**Exact command launched:**
```
.venv/bin/python scripts/agent_golden_run.py \
  --config .factory/golden-runs/golden-run-056-config.yaml \
  --spec-yaml tests/fixtures/url-shortener/spec.yaml \
  --decomposer-channel opencode \
  --decomposer-model fireworks-ai/accounts/fireworks/routers/kimi-k2p6-turbo
```

**Caveat — the wrong-call surface:** GR-055's exact `agent_golden_run.py`
invocation was NOT recoverable from the repo (the launcher does not log its own
args; worklog/reflections/run-logs don't record it). The decomposer
channel/model above is a *deliberate explicit choice* — `opencode` is
`populate_work_items.py`'s default channel; `kimi-k2p6-turbo` is the run's
primary worker model — NOT a confirmed match to how 055 decomposed. **If GR-056
diverges from 055 in ways unrelated to the WS-1/2/3 fixes, suspect the decomposer
channel/model first** and re-run with 055's actual decomposer once recovered.

**Config:** `golden-run-056-config.yaml` = `golden-run-055-config.yaml` with only
`project_name` (sf2_golden_056) and `workspace_root` (/tmp/sf2-golden-056)
changed. The fixes under test (WS-1a/b, WS-2, WS-3) are **uncommitted** in the
sf2 working tree at launch time (git ≤ GR-052).

### GR-056 outcome (2026-05-31)

Completed (launcher exit 1 was a benign post-run cleanup guard refusing to rmtree
a non-`/tmp` logs dir; `verify_passed: True`). **Directional win:** 0
`review_found_defect` (vs 055's 17 — WS-1 vacuous-test class eliminated);
first-gate-eval pass 73% (cleared the ≥60% bar 055 missed at 57%); deaths were
legitimate (mypy/pytest/jury), not test-theater. **But not a clean WS-2
validation:**
- The boot probe *fired* (conformance events present; 055 had 0) but **could not
  execute**: `conformance_pip_install_failed: No module named pip` — the `uv
  venv` gate env has no bundled pip, and conformance used `<exe> -m pip`. So
  FastAPI never installed and the app never booted. (The `spec_yaml_parse_failed`
  debug log was benign — the heading-style fallback extracted AC-BOOT-01.)
- **The recorded decomposer-divergence caveat materialized:** 11 work items (3
  modules) vs 055's 50 — the kimi decomposer produced a much smaller set. Not
  apples-to-apples; percentages noisy.

**Fix applied (working tree):** `gate/conformance.py` now installs requirements
via `uv pip install --python <exe>` when uv is present (mirrors `factory.venv`),
falling back to module-pip only without uv. Verified: the failing op reproduces,
the fixed op installs FastAPI; conformance unit tests pass (40).

### GR-057 — relaunch (2026-05-31)

Same Form A command as 056 (only `project_name`/`workspace_root` → 057). The
only behavioral change vs 056 is the conformance pip fix above. **Validation
target:** `conformance_pip_install_failed` gone, boot probe actually executes the
app (the WS-2 proof 056 couldn't deliver). Decomposer divergence (run scale) is
unaddressed here — revisit separately if a 055-scale comparison is needed.

### GR-057 outcome (2026-05-31)

Completed (launcher exit 1 = the same benign cleanup guard). **pip fix
confirmed:** 0 `conformance_pip_install_failed` (vs 056 blocked). Lock 72%
(13/18), first-gate-eval 72% PASS, 0 `review_found_defect` (WS-1 holds across two
runs). Decomposition varied again (18 items; 50→11→18 across 055/056/057 —
decomposer-divergence caveat stands).

**WS-2 boot-probe efficacy — VALIDATED by controlled experiment** (not by the GR
alone, whose ~1s conformance pass was ambiguous). Ran `evaluate_module_boot_probe`
on three modules with a production-shaped uv gate venv:
- FastAPI app with `/healthz` → **PASS** ✓
- no-app stub → **FAIL** ✓ (anti-vacuity holds — a non-HTTP module cannot pass)
- FastAPI app, no `/healthz` but `/docs` fallback → **PASS** ✓

So the executed boot probe genuinely boots the app and enforces the anti-vacuity
guarantee. Combined with the pip fix, the AC-BOOT-01 item that passed conformance
in 057 was a real boot, not a trivial pass.

**New follow-ups (filed):** BC-229 (unknown-gate telemetry classification gap,
4.9% FAIL — a new gate name / WS-2 conformance-at-impl combo telemetry doesn't
bucket; cosmetic, not a correctness bug); BC-230 (launcher cleanup exits 1 on
non-`/tmp` logs, making successful runs report as failed). `mean attempts 2.28`
still FAILs (≤2.0) but on small/variable samples.

**Net:** WS-1 + WS-2 are validated (vacuous class gone; boot probe executes and
enforces). Remaining: the two telemetry/launcher follow-ups, and a 055-scale
clean comparison if desired (decomposer divergence).

### GR-058 — relaunch on committed fixes (2026-05-31)

Same Form A command (only project_name/workspace_root → 058). Unlike 056/057,
**all fixes are committed** (conformance uv-pip fix, BC-229 telemetry, BC-230
cleanup-exit, BC-231 config-opencode) — so this run is reproducible from git.
Validation targets: (1) opencode workers no longer `channel_fail` (BC-231
config-opencode.json now exists); (2) unknown-gate rate back to 0% (BC-229);
(3) launcher exits 0 on success (BC-230); (4) WS-1/WS-2 hold (0 vacuous
rejections; boot probe executes). Decomposer still kimi (scale varies run-to-run).

### GR-058 outcome (2026-05-31) — ALL PASS

First fully-green run of the cycle. Lock 79% (11/14), mean-attempts 2.00 (PASS,
cleared ≤2.0 for the first time), first-gate-eval 79%, unknown-gate 0.0%,
deterministic gate 86%, stuck 0 — **Overall: ALL PASS**, verify_passed True.
All fixes validated composing on committed code: BC-231 (0 channel_fail / 0
config-opencode ENOENT), BC-229 (unknown-gate 0%), BC-230 (launcher exit 0),
WS-1 (0 review_found_defect), WS-2 (conformance fired, 0 pip failures). This run
is reproducible from git (unlike 056/057). Decomposer divergence persists (14
items vs 055's 50) — the one remaining open question is a 055-scale comparison.
