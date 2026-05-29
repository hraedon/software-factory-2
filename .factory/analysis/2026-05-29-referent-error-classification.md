# Failure classification: do "mechanical referent errors" dominate the corpus?

**Date:** 2026-05-29
**Author:** classification pass over GR-001 … GR-047 + defect-class taxonomy + RFCs
**Question:** A socratic-specification design note proposed adding an upstream
"component manifest" (stable IDs + interfaces, lintable so no implementation
references an undeclared referent) on the premise (its "Fact 1") that *the real
failures we've seen are mechanical referent errors — implementers wiring
components to things that don't exist, inventing functions.* This doc tests that
premise against the golden-run corpus and classifies what actually blocks runs.

## Verdict in one line

Fact 1 was real but is **already solved** — by RFC-015's *projected* import
manifest — and the residual failures that dominate the corpus are pipeline/harness
defects and genuine model reasoning failures (mypy/pytest), neither of which a
referent manifest addresses. The invented-referent bucket is the one bucket that
is closed.

## The proposed mechanism already shipped here

**RFC-015 — "Dependency import manifest + gate-level import validation"**
(`breadcrumbs/resolved/RFC-015-*.md`, `status: implemented`) is the proposed
mechanism, built and validated:

- AST-walks the locked `.pyi` stubs to extract the exported symbol set (the
  enumerable "set of existing things").
- Injects a compact `available_dependency_imports` manifest into the
  implementer / test-author prompt.
- Gate check: `from <module> import <symbol>` where `symbol ∉ exports` fails
  with the available-symbol list as feedback (`GATE_NAME_INNER_IMPORT_SYMBOLS`,
  first in the inner-gate cascade).

RFC-015's own problem statement is Fact 1 almost verbatim: *"the model generated
code referencing symbols that don't exist in dependency modules. Example:
`certificate_model has no attribute parse_certificate`."*

### The critical design property: projected, not authored

RFC-015 works because the referent set is **mechanically projected from locked
artifacts** — it is ground truth, AST-walked from already-verified `.pyi` stubs.
The lint checks the implementation against reality. The socratic proposal instead
has the **soliciting agent author** the manifest as upstream YAML, which inverts
the source of validity: the lint would then verify the implementation is
consistent *with the manifest*, not with reality. An authored manifest can be
confidently wrong and still pass its own lint (see GR-045 below).

## Before / after: what the manifest actually bought

| Metric | GR-019 (pre-manifest) | GR-020 (post-manifest) |
|---|---|---|
| Inner-gate first-attempt pass | 64% (7/11) | 77% (20/26) |
| "Module X has no attribute Y" failures | 3 of 4 inner-gate failures | **0 across the run** |
| First-attempt failure modes | dominated by invented-symbol imports | `inner_import_check` (runtime, recovers on retry) + `inner_mypy` (type reasoning) |
| Lock-within-budget | — | 100%, 0 stuck |

The principal's RFC-015 acceptance note predicted the residual exactly: *"The
remaining 20% will be genuine mypy/pytest failures that need model reasoning, not
symbol lookup."* The corpus confirms it (GR-044: psycopg2 type confusion +
pytest assertion; GR-009/010: `leaf=None` runtime logic).

## Bucket classification (every failure that drove cannot_proceed / blocked a run)

| Bucket | Evidence | Caught by a referent manifest? |
|---|---|---|
| **Pipeline / harness defects** (dominant by class count) | CLASS-001 contract-validation entry-point drift (10 inst, critical); CLASS-002 module-name resolution (5, high); CLASS-008 gate venv mismatch (GR-032/046); CLASS-010 channel reliability (GR-042); escalation no-op (GR-002) | No — orthogonal |
| **Invented-symbol referent errors** | GR-019 | **Yes — already fixed by RFC-015** |
| **Type-safety reasoning** (mypy) | GR-003 (ruff UP/I style), GR-008 (empty-body stubs), GR-032, GR-044 (psycopg2) | No |
| **Runtime logic** (pytest) | GR-009/010 (`leaf=None`), GR-044 | No |
| **Spec-level confabulation** | GR-045: decomposer hallucinated an entire FR-05 with content bled from another workload | **No — see below** |
| **Architectural divergence** | GR-047: K2 vs Sonnet jury disagreement on HTTP handler / Pydantic / route patterns | No — this is Claim-2 territory, empirically |

Note CLASS-002 ("Dependency Module Name Resolution") looks referent-shaped but is
not the model inventing referents — it is the *harness* deriving module names from
fragile sources (spec-title regex). The model used correct names; the gate
environment failed to make them resolve (GR-002/006a/008/012/013). That is the
inverse of Fact 1.

## GR-045: why an authored manifest does not close the spec-level case

GR-045's decomposer confabulated a whole component (FR-05) from context bled in
from a prior workload. A referent lint over a manifest *containing* that
hallucinated component passes cleanly — the component has a stable ID and
consistent interfaces; it simply should not exist. The failure was not ambiguity;
it was confident wrongness, traced to session contamination (BC-220) and fixed
with a fresh session (GR-046) — not by any schema. This is the spec-level analog
of the projected-vs-authored distinction: an upstream-authored manifest gives you
lint-able IDs, not ground truth.

## Implications for the socratic-specification design note

1. **Drop the "attacks Fact 1's mechanical referent errors" framing.** At the
   implementation/symbol level that class is empirically closed (RFC-015).
   Re-deriving it upstream is reinventing a shipped mechanism — and the honest
   pitch is: "sf2 proved a *projected* manifest eliminates invented-symbol
   imports; socratic asks whether an *authored* manifest can do the same one
   level up, at component/interface granularity."

2. **That reframing puts the proposal in Claim 2, not Claim 1.** The validity
   question becomes "who establishes that the authored manifest corresponds to
   reality?" — and the corpus (GR-045/047) says the answer is a cross-model
   fitness pass, not a schema constraint. This matches socratic's own
   `critique.md:98` (DeepSeek review of debate 005), which independently argued
   the composition checks should be "a structural parse (symbol table → list of
   unreferenced export symbols)" run by a *different model instance*, not the
   author.

3. **The Claim-1-clean win is the boring bucket.** The harness defect classes
   (CLASS-001/002/008/010) are what actually block golden runs today. None are
   spec-quality problems; none are helped by a manifest.

## Sources

- `breadcrumbs/resolved/RFC-015-dependency-import-manifest-gate-validation.md`
- `.factory/golden-runs/golden-run-{019,020,044,045,046,047}-log.md`
- `breadcrumbs/CLASS-{001,002,008,010}-*.md`
- `/projects/socratic-specification/{critique.md,debate/resolved/005-composition-audit.md}`
