---
number: "126"
title: "Work-item granularity correlation — measure AC count vs first-attempt pass rate, then cap"
severity: high
status: resolved
kind: improvement
author: opus-review
date: "2026-05-12"
tags: [spec, work-item, first-attempt, prompt, phase-3]
related: ["122", "RFC-013", "RFC-015"]
---

## Resolution

Phase A measurement complete. Analysis report at `.factory/analysis/2026-05-13-work-item-granularity.md`.

Conclusion: **The hypothesis is not supported.** Across 96 work-item rows (43 with clean inner-gate signal from GR-019+020), first-attempt pass rate is flat across AC counts 4–10. Pearson correlations are near zero and slightly positive (r = +0.11 for AC count, +0.03 for spec words, +0.03 for dep lines). No knee in the curve. No monotonic decline. Larger work items actually lock at slightly higher rates.

No spec-lint size cap warranted. BC-126 closed without Phase B action. The 10 first-attempt failures that remain are import-resolution and mypy generic-type errors — structural issues, not size issues. These are better addressed by RFC-015 (dependency import manifest) than by work-item splitting.

## Problem

Output quality is suspected to be steeply nonlinear in work-item size, but the relationship has never been measured in sf2. We optimize prompts, gates, and dependency context for the *current* distribution of work-item sizes. If that distribution skews large, every other quality lever is fighting upstream.

Anecdotal evidence from GR-015 → GR-019:

- The cert-watch DAG has work items ranging from 2 ACs (`certificate_model`) to 14 ACs (`cert_chain_library`).
- `cert_chain_library` is the work item that timed out in GR-019. It is also the largest.
- The 0% → 64% first-attempt jump between GR-015 and GR-019 came from prompt/gate work, but the failures that remain are concentrated on the larger work items.

This is unconfirmed because we have not actually measured it. We are guessing from session reflections.

## Proposed work

Two phases. Phase A is measurement and cannot be skipped; phase B depends on phase A's answer.

### Phase A — Instrument and measure (no behavior change)

1. Add a `work_item_size_metrics` extraction tool at `scripts/work_item_size_metrics.py` that, given a project config + run telemetry, emits a CSV:

   ```
   work_item_id, role, ac_count, spec_word_count, dep_count, dep_total_pyi_lines,
   first_attempt_passed, retry_count, gate_label_on_first_fail, locked
   ```

   - `ac_count`: count of bullets in the `## Acceptance Criteria` section of the spec.
   - `spec_word_count`: total words in the spec body (excluding frontmatter and dependency injection).
   - `dep_count`: number of locked dependencies.
   - `dep_total_pyi_lines`: sum of line counts across all injected `.pyi` stubs.
   - `first_attempt_passed`: whether retry=0 cleared the inner gate.
   - `retry_count`: how many inner-gate retries.
   - `gate_label_on_first_fail`: which gate failed first on retry=0 (use the existing cascade labels: `inner_ruff`, `inner_mypy`, `inner_import_symbols`, `inner_pytest`, etc.). Empty if first attempt passed.
   - `locked`: terminal lock state.

2. Backfill the CSV across all historical golden runs in `runs/` that have surviving telemetry. Discard rows where telemetry is incomplete (e.g., GR-019's contamination). Aim for ≥ 100 work-item rows across ≥ 6 clean GRs.

3. Run three correlation analyses (Pearson; this is exploratory, not inferential — don't over-engineer the stats):
   - `ac_count` vs `first_attempt_passed`
   - `spec_word_count` vs `first_attempt_passed`
   - `dep_total_pyi_lines` vs `first_attempt_passed`

4. Bucket and plot: first-attempt pass rate at `ac_count ≤ 3`, `4-6`, `7-10`, `> 10`. The shape of the curve matters more than the correlation coefficient.

5. Save the analysis to `.factory/analysis/2026-05-XX-work-item-granularity.md` (one report file; don't add a recurring dashboard yet).

### Phase B — Act on the answer

**Decision branches based on phase A:**

- If the curve is flat (no relationship between size and first-attempt rate): close this BC. The hypothesis was wrong; spend effort elsewhere. This is a valid outcome.

- If the curve has a clear knee (e.g., first-attempt rate drops sharply above ≥ 7 ACs): add a spec-lint rule (see BC-127) that warns on work items above the knee. Document the threshold in `AGENTS.md`. Do NOT auto-split — splitting is a human judgment call because dep edges have to be re-thought.

- If the curve is monotonically declining without a knee: every AC matters. Different conversation — escalate to a design discussion before acting.

### Phase C (deferred — not part of this BC)

A `scripts/suggest_work_item_split.py` tool that proposes decompositions for oversized specs is **explicitly deferred**. Do not build it as part of this BC. It only becomes a candidate if:

1. Phase A confirms a knee, AND
2. BC-127's lint cap surfaces oversized specs frequently enough to justify tooling beyond human judgment, AND
3. The principal asks for it.

Building a suggestion tool before knowing whether the problem exists is the exact failure mode this BC is trying to avoid. If Phase C is ever opened, file it as its own BC.

## What this is NOT

- Not a hard cap on work-item size at filing time. Caps before measurement are guesses dressed as rules.
- Not a refactor of the cert-watch DAG. Don't go retroactively splitting work items in the test fixtures; the cert-watch sizing is a sample of real-world variance and useful as-is.
- Not a model-routing system ("send big work items to a bigger model"). Out of scope; revisit only after Phase B.
- Not a "complexity score" beyond AC count, word count, and dep lines. The whole point is using cheap, mechanical signals. If those don't predict, more sophisticated metrics probably won't either.

## Validation criteria

- Phase A CSV covers ≥ 100 work-item rows across ≥ 6 GRs.
- The analysis report explicitly answers: "Does size predict first-attempt failure? Where is the knee, if any?"
- If a knee is found, the spec-lint rule (BC-127) lands within 2 sessions of the analysis.
- The analysis result is referenced in the next golden-run nanny report so the threshold (if any) is acted on.

## Suggested PR shape (Phase A)

1. `scripts/work_item_size_metrics.py` — new, extracts the CSV.
2. `tests/test_work_item_size_metrics.py` — extraction unit tests against a fixture run.
3. `.factory/analysis/2026-05-XX-work-item-granularity.md` — the analysis report.

No code changes to `factory/`. No new gates. No prompt changes.

## Phase placement

Phase 3 (current). Measurement is cheap; the decision is the expensive part. Run measurement before Phase 4 begins so the work-item shape question is settled before jury/race amplifies whatever sizing pathology exists.
