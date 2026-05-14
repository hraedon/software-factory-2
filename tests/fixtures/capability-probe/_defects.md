# Capability-Probe Answer Key

**Do not show this file to models under evaluation.** It records the defects
deliberately planted in `wi_rate_limiter.md` so scorers can grade per-role
outputs against the BC-137 rubric.

## Planted defects

| ID | Defect | Category | Location |
|----|--------|----------|----------|
| D1 | `consume` signature says `-> bool` but AC-02 body says it returns the number of tokens remaining (int) | Type ambiguity | AC-02 |
| D2 | AC-03 says `consume` returns `None` on insufficient tokens; AC-04 says it raises `RateLimitExceeded` when the bucket is empty | Contradictory ACs | AC-03 vs AC-04 |
| D3 | AC-06 references `clock.monotonic_seconds() -> float`; the Dependencies block declares only `clock.monotonic_ns() -> int` | Impossible dependency | AC-06 vs Dependencies |
| D4 | AC-05 refill formula is silent on negative `elapsed` (clock skew, first-seen key), on `refill_per_second <= 0`, and on floating-point drift across many small consumes | Underspecified edge | AC-05 |
| D5 | Nothing said about: `tokens <= 0`, `tokens > capacity`, unknown-key first-seen behavior, concurrent `consume` on same key, eviction race with in-flight `consume` | Missing error case | spec-wide |

## Per-role expectations

| Defect | interface_architect | test_author | implementer | cross_family_reviewer | frontier_judge |
|--------|--------------------|-------------|-------------|-----------------------|----------------|
| D1 | Pick one return type and commit in `.pyi` | Tests fail to type-check or contradict each other = fail | Match committed `.pyi` | Must flag | Must flag |
| D2 | Reject or amend before producing interface | N/A¹ | N/A¹ | Must flag | Must flag |
| D3 | Must reject or amend (cannot import nonexistent function) | N/A¹ | N/A¹ | Must flag | Must flag |
| D4 | Make negative-elapsed and zero-rate behavior explicit | Test the gaps | Defensive impl (clamp elapsed >= 0, reject rate <= 0) | Note the gap | Note the gap |
| D5 | Make at least negative-tokens and `tokens > capacity` explicit | Test those cases | Reject invalid inputs | Flag at least one | Flag at least one |

¹ **N/A** for test_author and implementer on D2/D3: these roles receive the *locked interface* in production, not the raw dependency block. The interface architect has already resolved (or failed to resolve) contradictions and impossible dependencies before these roles see the artifact. Evaluating test_author/implementer on D2/D3 requires giving them a deliberately flawed interface, which is non-standard; the hard-floor rule therefore applies only to roles that see the raw spec or the full bundle (interface_architect, cross_family_reviewer, frontier_judge).

## Scoring

For each (model, role) cell:

- **Pass**: model's output addresses the defect appropriately for its role per
  the table above.
- **Partial**: model notices the defect but handles it weakly (e.g., reviewer
  mentions D2 in passing without calling for rejection, or a role without a
  structured-failure channel embeds a note in a docstring/`assert False` test
  rather than producing a formal refusal).
- **Fail**: model produces output that silently accepts the defect or
  introduces a new defect by misinterpreting it.

Hard floor: any model that fails on **D2 or D3** for any role is unfit for that
role. D2 and D3 are both objective contradictions; missing them indicates the
model is not reading the spec critically. For test_author and implementer, D2/D3
are evaluated only when the upstream interface deliberately preserves the defect;
in that scenario, a "Pass" requires the model to either produce a `cannot_proceed`
JSON block (if the prompt supports it) or to explicitly document the flaw in a way
that a downstream gate would reject the artifact.

D4 and D5 separate "competent" from "rigorous" — useful for selecting the
strongest model for `frontier_judge` and `cross_family_reviewer`.

## Methodology notes

- Run each model at single-attempt with the inner gate disabled (per BC-137 §Methodology).
- Use the same prompt template the pipeline uses in production for that role.
- Capture raw output, not just pass/fail — qualitative review is part of the
  evaluation, especially for D4/D5.
- Record results in `.factory/analysis/YYYY-MM-DD-model-capability-evaluation.md`.
