# software-factory v1 — adversarial review from a sf2 perspective

*Written 2026-05-18 to fill a blind spot: I've reviewed substrate and sf2 extensively this session but never touched v1, which sf2 cites as the source of many of its design decisions. Frame: what is v1 doing that sf2 hasn't yet learned from, and where would I focus a deeper-look pass?*

Source: Explore agent survey of `/projects/software-factory` + spot-reads of BC-383 (FR agents miss production wiring), BC-376 (Fireworks env breaks native auth), BC-314 (containerized validation), BC-120 (convoy/bead decomposition), BC-300 (infrastructure pattern library). Cross-referenced against sf2's `breadcrumbs/` to see which lessons have crossed over.

## Topline assessment

v1 is on **late life-support tending toward active**: 461 .py modules, ~92.5K LoC, 2198 tests, 403 breadcrumbs, last meaningful commit 2026-05-04 (14 days ago, BC-383 in-progress). It is **not** a dead codebase. It is the slower-moving sibling to sf2 — still receiving bug fixes, still the validation reference for real-world pipeline behavior, and still surfacing new defect classes that sf2's spec hasn't yet anticipated.

**My pick:** v1 is worth keeping alive *as a defect-class sensor*. The architecture is structurally inferior to sf2's event-sourced model and shouldn't be re-invested in for new features — but the BCs it produces are the closest thing you have to a production datastream. Don't archive it. Continue to mine BCs from it as inputs to sf2.

## Lessons absorbed by sf2 (good)

The cross-referencing turned up four v1 lessons sf2 has explicitly inherited:

| v1 BC | sf2 absorption | Status |
|---|---|---|
| BC-383 (prompt conflict — ownership vs review) | sf2 RFC-001 (prompt conflict detection) | resolved |
| BC-376 (env var injection breaks native auth) | sf2 RFC-003 (channel adapter auth-mode detection) | proposed |
| string-constant gravity / two-copies-diverge | sf2 RFC-011 (unified gate evaluation layer) | implemented |
| ownership rules + skeleton plan mismatch | partial absorption via RFC-001 + RFC-030 family | partial |

The discipline of citing v1 BC numbers in sf2 RFCs and breadcrumbs is excellent. It makes the lessons traceable. Don't lose that habit.

## Lessons NOT yet absorbed by sf2 (the actual review)

Three open v1 BCs that look like they will become sf2 problems if left:

### 1. BC-383 (production wiring): the *symptom* is closed in sf2 (RFC-001 detects prompt conflicts) but the *class* is open

v1 BC-383 names three interacting root causes: implementer prompt doesn't say "wire production deps," ownership prompt says "shared-frozen = read-only" when it isn't, and the skeleton plan declares files it doesn't emit. sf2's RFC-001 catches the prompt-contradiction half of this. It does **not** catch:

- A role whose prompt says "make tests pass" but whose tests pass via mocks. This is structural to the implementer role definition. Until the implementer prompt says "tests passing via mock-override don't count as done," the *same* defect can surface in sf2 the moment a role does mock-based DI.
- A skeleton/interface artifact that declares an intent but the downstream stage doesn't enforce. sf2's `interface_spec → implementation` handoff is the analog of v1's `skeleton → fr-implementer`. Has anyone audited whether sf2's interface_spec can declare a file or function that the implementer is then allowed to silently skip?

**Suggested follow-up:** file a sf2 BC for "implementer must distinguish between tests-pass-via-mocks and tests-pass-against-production-DI." The honest test is `pytest --no-overrides` or equivalent — run the test suite without conftest fixtures available. If it still passes, the production wiring is complete. If it 500s, there's a wiring gap.

### 2. BC-314 (containerized validation environment) — sf2 has no analog

v1's BC-314 names the gap: post-merge code might pass tests on the host but fail in a clean container due to framework/dependency version skew. sf2 has the same gap — `outcome_verification` runs in the sf2 process's environment, not a clean one. Cert-watch fixture has dodged it because the fixture's deps overlap sf2's; a different-shape fixture would expose it.

**Suggested follow-up:** sf2 BC: "outcome_verification stage runs in caller's env, not a clean container — drift between dev and target deploy will pass locally and fail at deploy." Could be Phase-5 work, won't bite until a non-cert-watch fixture lands.

### 3. BC-120 (convoy/bead model) — decomposition is rigid in both

v1 BC-120 calls out that decomposition is fixed at architect-time; no mid-flight splitting of an overlarge work unit, no bundling of related small ones. sf2 has the same constraint — interface_spec produces a fixed AC list, the implementer can't request "this is too big, split it" or "let me bundle these two." This is one of the more under-addressed v1 lessons.

sf2 RFC-022 (initiative bundling) and RFC-023 (decomposer role) gesture at this but neither is implemented. Worth promoting if you want fleet expansion to do anything more interesting than "more channels on the same rigid stage graph."

## Where I'd focus a deeper look

Based on the Explore survey, three v1 modules are worth opening if anyone wants to do the next deeper pass:

1. **`factory/agents/tools/ownership.py` + `factory/agents/prompts.py`** — root of BC-383, and the closest v1 analog to sf2's per-role prompt construction. Comparing v1's ownership-rule generation against sf2's role/channel binding might surface invariants sf2 should be enforcing too.

2. **`factory/stages/merge.py` (34 KB)** — v1's most semantically-loaded stage. sf2's `integration` stage is the analog and is smaller. The complexity gap is interesting: did sf2 simplify by externalizing concerns (e.g. relying on git's own merge), or by deferring problems?

3. **`factory/stages/fr_review/main.py`** — v1's per-FR adversarial review. sf2's `cross_family_review` is the analog. v1's review can call back into "fix agents"; sf2's flows to `upstream_revision`. The retry/fix loop topology is materially different — worth understanding which works better empirically.

## Structural observations

- **v1 is a script.** ~461 modules of synchronous staged code, file-IO heavy, no event log. sf2's choice to build on substrate (event-sourced) is the right call long-term. v1's defects are *consequences* of the script-style architecture: stages can't replay, can't fork, can't resume cleanly.
- **v1 has discovered defect classes sf2 hasn't named yet.** The 403 v1 BCs are an asset. A periodic "diff v1 BC titles against sf2 BC titles, surface ones unique to v1" exercise would compress a lot of unhappy future.
- **A-MEM (`sentence-transformers` + Postgres) was a real bet.** Worth knowing whether it paid off — if not, the lesson "embedding-graph knowledge stores are heavyweight for marginal benefit" is a v1-derived signal sf2 should encode before someone proposes building one.

## Recommendation

**Continue treating v1 as a defect-class sensor, not a software product.** Concretely:

1. **One follow-up BC in sf2**: "implementer must run tests without conftest overrides as a separate pass" (the BC-383 class). High signal-to-noise.
2. **One follow-up BC**: "outcome_verification needs a clean-env mode" (BC-314 class). Phase-5 priority.
3. **Periodic v1→sf2 BC diff** (monthly?). The v1 corpus is producing defect-class signal at low cost; sf2 should be a consumer.
4. **No new feature work in v1**. Bug fixes only. The architectural cap is real; investment goes into sf2.

The growth-project recommendation in `2026-05-18-growth-project-recommendation.md` (eval harness) would naturally consume v1's BC corpus as one of its evaluation inputs — a real-world dataset of agentic-pipeline defects to grade newer agents against. Worth designing the eval harness so v1's BCs are a tier-1 evaluation set.
