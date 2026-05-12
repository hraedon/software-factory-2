---
number: "128"
title: "Cross-attempt defect taxonomy — classify model-attempt failures across GRs"
severity: high
status: implemented
kind: improvement
author: opus-review
date: "2026-05-12"
tags: [observability, telemetry, inner-gate, analysis, phase-3]
related: ["122", "126", "127", "RFC-014", "RFC-016"]
---

## Problem

Every prompt change, gate change, spec change, and dep-context change in sf2 is currently evaluated on vibes. The kimi-k2 reflection from session 25 said this directly: "I can't tell if the 64% first-attempt rate is due to checklists, auto-fix, or model variance."

This is the wrong baseline for entering Phase 4. Phase 4 introduces jury/race, which multiplies model invocation cost. Spending more on samples without knowing which defect classes those samples are biased against is expensive guesswork. Before jury, we need to know: when an attempt fails on retry=0, *what kind* of failure was it? And how does that distribution change as we ship interventions?

This is distinct from RFC-016 (defect-class taxonomy at the project-defect level). This one operates at the model-attempt level: every individual inner-gate failure across every GR.

## Proposed work

Build a corpus + a one-page report. No live dashboard. The corpus is the artifact; the report is the readable form.

### Corpus

A single file `runs/_corpus/inner_gate_failures.jsonl`, append-only, one JSON line per inner-gate retry=0 failure across all golden runs (historical and going forward).

Each line:

```json
{
  "gr_id": "GR-019",
  "work_item_id": "d75ba24b",
  "role": "implementer",
  "attempt": 0,
  "gate_label": "inner_mypy",
  "feedback_excerpt": "first 500 chars of the gate-feedback string fed back to the model",
  "category": "type_mismatch_library_api",
  "subcategory": "cryptography.x509",
  "fixed_on_retry": 1,
  "fixed_on_retry_label": null,
  "model": "kimi-k2p6-turbo",
  "channel": "opencode",
  "ts": "2026-05-12T03:24:11Z"
}
```

`category` and `subcategory` are the human-classified columns. Everything else comes from existing telemetry.

`model` and `channel` are recorded separately because they are not the same thing — the opencode channel serves multiple models (kimi, glm, deepseek), and a channel-level failure (empty output, timeout) is signal about the adapter, while a model-level failure (wrong API usage) is signal about the model. Conflating them contaminates both analyses.

### Categories (initial set; mutable)

The categories below come from inspection of GR-008 through GR-019 reflections. Treat as a starting point; add/merge categories as the corpus grows.

1. **`ruff_style`** — formatting, import sort, unused vars. Pure mechanical.
2. **`import_unknown_symbol`** — `from x import y` where y doesn't exist. (RFC-015 target.)
3. **`import_module_path`** — module resolution / path issue (BC-072/077/084 territory).
4. **`type_mismatch_library_api`** — model used a library API incorrectly (wrong signature, wrong type). DeepSeek's pattern in GR-018.
5. **`type_mismatch_internal`** — type error on internal/locked types.
6. **`mypy_missing_annotation`** — annotation absent on a public function.
7. **`pytest_assertion`** — test assertion failed against implementation.
8. **`pytest_collect_error`** — test file failed to collect (often an import error wearing a different hat).
9. **`pytest_fixture_missing`** — fixture not found or wrong scope.
10. **`spec_ambiguity`** — model output is correct but spec was ambiguous, gate caught the wrong interpretation. Hardest to classify; requires judgment.
11. **`channel_failure`** — empty output, timeout, parse error. Not a model-quality issue; tracked separately so it doesn't contaminate the distribution.
12. **`other`** — escape hatch. If `other` exceeds 10% of corpus, the taxonomy needs revision.

### Tool

`scripts/build_failure_corpus.py`:

1. Reads `runs/GR-*/` telemetry directories.
2. For each retry=0 inner-gate failure, extracts the structured fields automatically.
3. The `category` / `subcategory` columns are auto-filled where possible by `runs/_corpus/classification_rules.yaml` — a YAML file mapping regex patterns over `feedback_excerpt` (and `gate_label`) to categories. **The rules file ships from day one, populated with the ~10 most obvious patterns.** Interactive classification is the escape hatch for unmatched rows, not the primary mechanism.
4. A separate command (`--classify`) walks rows where `category: null` and prompts the operator. The operator's choice is written back to the row *and* may be promoted into the rules file (the operator is asked "add this pattern to rules.yaml?"). This makes the rules file grow with the corpus rather than requiring a separate maintenance pass.
5. Persists classification state. A row is only ever classified once. New GRs add new rows.

Rationale for rules-first rather than prompt-first: interactive classification is slow and rots first. The rules file is grep-able, versionable, and self-documenting. Every operator-supplied label that isn't a one-off should land in the rules file the same session.

### Report

`scripts/failure_corpus_report.py`. Reads the corpus, emits a one-page markdown report to `.factory/analysis/failure-corpus-latest.md`:

```
# Inner-gate failure corpus — N=247 (GR-008 through GR-019)

## Distribution

| Category | Count | % | Trend (last 3 GRs vs prior) |
|---|---|---|---|
| ruff_style              | 47 | 19% | ↓↓ (eliminated by BC-122/123/124) |
| import_unknown_symbol   | 38 | 15% | → |
| type_mismatch_library   | 31 | 13% | → |
| ...                                                       |
| other                   |  4 |  2% |   |

## Top growing categories
1. type_mismatch_library_api — up from 8% to 14% over GR-017..019
2. ...

## Top shrinking categories
1. ruff_style — from 31% to 4% post-BC-123
2. ...

## Open questions
- pytest_assertion is flat across 6 GRs. No intervention has moved it. Candidate for next investment.
- spec_ambiguity is 7%, but classification confidence is low. Re-examine after BC-127 lands.
```

The report is regenerated by hand at end of every GR's nanny session. Not automated; the human-in-the-loop is the point.

## How this feeds every other lever

- **BC-122 (pre-flight checklists)**: did `ruff_style` actually drop after this landed? The corpus answers yes/no with a number.
- **RFC-015 (import manifest)**: did `import_unknown_symbol` drop? Will be visible in GR-020.
- **BC-126 (work-item size)**: cross-tabulate category × ac_count. Do larger work items fail differently from smaller ones?
- **BC-127 (spec lint)**: classify the historical specs against `spec_ambiguity` retries. Did lintable patterns predict ambiguity failures?
- **Phase 4 jury design**: the category distribution tells you what kind of variance jury can fix (sample variance on `type_mismatch_*`) and what it can't (`spec_ambiguity` won't improve with more samples).

Without the corpus, every one of these questions is unanswerable.

## What this is NOT

- Not a real-time dashboard. JSONL on disk + a markdown report regenerated by hand. No services, no daemons, no UI.
- Not an LLM classifier. Categories are human-assigned. Regex rules are allowed; the model is not the classifier.
- Not a per-attempt classification (only retry=0). Including retries triples the corpus size with diminishing returns; the *first* failure is the signal of model quality. Later retries are signal of pipeline-recovery quality, which is a separate question.
- Not a substitute for nanny reports. Nanny reports describe one run. The corpus describes the distribution across runs.
- Not tagged by model in a way that enables A/B. The model field is recorded but cross-model comparison is contaminated by binding differences (different roles, different fixtures). Phase 4 will need a separate, cleaner A/B mechanism — don't try to extract it from this corpus.

## Risks

**Classification burden.** If labeling each new GR takes > 15 minutes, the system will rot. Mitigation: the regex rules file should absorb 80% of classifications within 2-3 GRs. If after 4 GRs the manual classification share is still > 50%, either expand the rules or accept that the corpus is for analysis sprints only, not continuous tracking.

**Category drift.** As the system improves, old categories empty out and new ones appear. Adding categories is fine; deleting them silently is not. When a category is retired, its rows are re-classified into the new category and a one-line note in `runs/_corpus/category_history.md` documents the change.

**Confirmation bias.** Once you have a number, you'll defend it. The corpus is a measurement tool, not an evaluation tool. Reports should state "this changed" not "this proves my intervention worked." Correlation, not causation.

## Validation criteria

- Initial backfill covers GR-008 through current. ≥ 200 rows expected.
- Classification rules file matches ≥ 80% of new rows within 3 GRs of going live.
- The first report (post-backfill) names the top 3 failure categories with counts and trend arrows.
- Within 2 GRs of each major intervention (BC-122, RFC-015, BC-127), the report shows whether the targeted category's share moved.
- Time to regenerate the report after a fresh GR ≤ 15 minutes.

## Suggested PR shape

1. `runs/_corpus/.gitignore` — keep classified data committed; ignore any local scratch files.
2. `runs/_corpus/inner_gate_failures.jsonl` — empty file, will be populated by the backfill.
3. `runs/_corpus/classification_rules.yaml` — starts with ~10 obvious regex rules.
4. `runs/_corpus/category_history.md` — one line: "2026-05-12: initial taxonomy".
5. `scripts/build_failure_corpus.py` — extraction + interactive classification.
6. `scripts/failure_corpus_report.py` — report generator.
7. `tests/test_failure_corpus.py` — extraction logic, rule matching, report rendering on fixtures.
8. `AGENTS.md` — one paragraph pointing nanny sessions at the corpus + report.

No changes to `runner.py`, `gate.py`, `pre_gate.py`, or prompts.

## Phase placement

Phase 3 (current), high priority. The corpus only becomes useful with N ≥ 100 rows, so the longer the start is deferred, the longer until Phase 4 starts informed. Build before BC-126 and BC-127 land — both of those need the corpus to evaluate themselves.

The ordering across this RFC + BC trio:

1. **BC-128 first** (this one). Provides the measurement substrate everything else evaluates against.
2. **BC-126 next** (work-item size). Cheap measurement; the analysis feeds threshold choice for BC-127.
3. **BC-127 last** (spec lint). The cap from BC-126 plus the category history from BC-128 give the lint sharp, evidence-backed thresholds.

Doing them in the opposite order leaves each one's value unmeasurable.
