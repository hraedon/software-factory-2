---
number: "127"
title: "Spec linting — pre-flight pass over work-item specs before model invocation"
severity: high
status: resolved
kind: improvement
author: opus-review
date: "2026-05-12"
tags: [spec, populate, lint, pre-flight, phase-3]
related: ["122", "126", "RFC-015"]
---

## Problem

The cheapest place to improve model output quality is the input. Every minute of model time spent disambiguating a vague AC, guessing what "robust" means, or hallucinating a missing dependency symbol is minute we paid for. The prompt pre-flight checklist (BC-122) addresses this on the *output* side — teaching the model to self-check before returning. There is no equivalent pass on the *input* side.

Concrete examples of spec problems that have cost retries across GR-008 through GR-019:

- ACs using un-measurable verbs: "should support", "must be efficient", "handle edge cases".
- ACs referencing symbols not present in the dependency `.pyi` stubs (precursor to the RFC-015 import problem — the spec itself was wrong).
- Specs with > 10 ACs where 3 of them are restatements of the same constraint in different words.
- ACs that mix interface-level claims ("function signature is X") with implementation-level claims ("uses caching") — the same AC can't drive both interface_architect and implementer.
- Missing AC numbers, duplicated AC numbers, AC bullets that span multiple unrelated requirements.

These are not model failures. They are spec-author failures the model is paying for.

## Proposed work

Add a spec-lint pass that runs before `populate_work_items.py` enqueues work and *before* any model is invoked.

### Tool

`scripts/spec_lint.py`. Reads a project config, walks each work-item spec, runs a fixed set of mechanical checks, emits structured findings.

### Checks (initial set — keep small)

Each check is one function in `src/factory/spec_lint.py`. Mechanical only; no LLM, no judgment calls.

1. **`check_ac_section_exists`** — spec has a `## Acceptance Criteria` section. Failure: error.
2. **`check_ac_bullets_well_formed`** — each AC is a bullet starting with `- AC-N:` where N is a unique integer. Failure: error. Catches the "missing/duplicated AC numbers" class.
3. **`check_ac_count_within_band`** — `len(acs)` in `[1, AC_SOFT_CAP]` where `AC_SOFT_CAP` is a new constant (default 8; revise after BC-126 lands). Above the cap: warning, not error. Below 1: error.
4. **`check_ac_uses_measurable_verbs`** — **deferred from v1; do not implement in this BC.** The original idea was an allowed/disallowed verb list. Two problems killed it: (a) domain-specific verbs that look subjective ("certifies" in a cert-watch context, "authorizes" in an auth context) are precise in context but would be flagged; (b) the allowed-verb list erodes by accretion, with no mechanical gate on additions. The right way to find out whether imprecise AC verbs predict failures is to let BC-128's failure corpus tell us — if `spec_ambiguity` correlates with specific verb shapes, *then* we add the check, with the verb list grounded in measured data rather than guessed. Skip this number in the implementation; do not renumber the others.
5. **`check_ac_symbol_references_resolve`** — for each AC, extract backtick-quoted identifiers (`like_this`). Cross-reference against the dependency manifest (same export map as RFC-015). If an AC mentions a symbol that doesn't exist in any locked dep AND doesn't appear in the spec's own declared signature, emit a warning. Failure: warning. This is the input-side mirror of RFC-015's output-side gate.
6. **`check_ac_single_concern`** — each AC bullet contains at most one of `and`, `or` at the top level. Above 1: warning. Catches "two requirements jammed into one AC."
7. **`check_spec_word_count`** — total spec word count below a soft cap (default 800). Above: warning. Captures the "spec is a wall of text" failure mode.

Default behavior: errors fail the lint pass and block `populate_work_items.py`. Warnings print and do not block. A `--strict` flag promotes warnings to errors for CI use.

### Wiring

`populate_work_items.py` calls `spec_lint(config) -> LintResult` before any work-item is created. On error: print the findings, exit non-zero, no work items created. On warning-only: print findings, proceed.

Add a `--skip-lint` escape hatch for the case where the lint is wrong and we need to ship anyway. Log a warning when used.

### Lint findings format

```
spec_lint: PASS / WARN / FAIL
specs/cert_chain_library.md:
  WARN [ac_measurable_verbs] AC-04: starts with disallowed verb 'supports'
                              -> use one of: accepts, returns, raises, validates, ...
  WARN [ac_count] 12 ACs (soft cap: 8)
  WARN [ac_symbol_references] AC-07 references `verify_chain` which is not in
                              certificate_model.pyi exports: Certificate,
                              CertificateChain, CertStatus
specs/certificate_model.md:
  PASS

Summary: 1 spec PASS, 1 spec WARN (0 errors, 3 warnings)
```

The format mirrors ruff output deliberately so reviewers read it the same way.

## Failure modes to guard against

Each of these is a thing v1 did. Don't repeat:

- **Don't let lint become semantic.** No "your AC seems vague" via LLM. The check list is purely lexical/AST. If a check requires judgment, it doesn't belong here — it belongs in human review.
- **Don't expand the verb list quietly.** Every addition to `SPEC_AC_MEASURABLE_VERBS` requires a one-line justification in the constant's docstring. The list grows by erosion if you don't gate it.
- **Don't auto-fix.** This is a lint, not a fixer. The author rewrites the spec; the tool does not.
- **Don't run during a golden run.** Spec lint runs at `populate_work_items` time, period. Mid-run lint adds nothing and risks blocking on a spec that was fine an hour ago.

## What this is NOT

- Not a replacement for human review. A spec that passes lint can still be a bad spec.
- Not a workflow change. Specs are still authored as today; the lint runs at populate time.
- Not coupled to RFC-015's import manifest by code — they share the export-map concept but the spec lint should re-extract or import the same `extract_exports` helper. Don't introduce a circular dependency between `spec_lint` and the gate.
- Not an LLM-based check. Mechanical only. If we want LLM review of specs, that's a separate RFC (and probably premature).

## Validation criteria

- Running spec lint on the cert-watch spec set produces a stable, deterministic report (same input → same output, byte-for-byte).
- Backfill the lint over GR-008 through GR-019 specs. Manually verify: do the warnings correlate with retry counts on those work items? If yes, the lint is detecting real signal. If no, the checks need tuning before they're enforced.
- A reviewer can fix all warnings on a typical spec in under 10 minutes.
- No spec author bypasses lint with `--skip-lint` more than once per session on average. (If they do, the checks are wrong.)

## Suggested PR shape

1. `src/factory/constants.py` — add `AC_SOFT_CAP` constant, `SPEC_WORD_COUNT_SOFT_CAP` constant. (`SPEC_AC_MEASURABLE_VERBS` is deferred — see check #4.)
2. `src/factory/spec_lint.py` — new module with the 7 check functions + `LintResult` dataclass + `spec_lint(config)` entry point.
3. `populate_work_items.py` — call `spec_lint(config)` before work-item creation, honor `--skip-lint` and `--strict` flags.
4. `tests/test_spec_lint.py` — one test per *implemented* check function (1, 2, 3, 5, 6, 7 — check #4 is deferred), against small inline spec fixtures. Plus an end-to-end test against the cert-watch spec set.
5. `AGENTS.md` — one paragraph documenting lint behavior and the escape hatch.

No changes to `runner.py`, `gate.py`, `pre_gate.py`, prompts, or substrate.

## Phase placement

Phase 3 (current). This is upstream of every model invocation, so it should land before the next golden run if possible. Cheap to build (≈ half a day), bounded scope, no model budget. If BC-126's measurement says "size predicts failure," check #3's cap becomes load-bearing immediately.
