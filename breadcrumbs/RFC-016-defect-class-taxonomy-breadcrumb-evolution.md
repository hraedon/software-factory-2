---
number: "RFC-016"
title: "Defect-class taxonomy — evolve breadcrumbs from per-defect entries to class-based corpus"
severity: medium
status: proposed
kind: design
author: opus-review
date: "2026-05-12"
tags: [breadcrumbs, process, taxonomy, meta, phase-3]
related: ["RFC-004", "RFC-014", "128"]
---

## Status note (2026-05-12, post-glm-review)

**Deferred behind BC-128.** This RFC proposes pattern recognition over the project-defect corpus (resolved BCs). BC-128 proposes the same shape of work over the model-attempt corpus (gate failures). The two have parallel structure but BC-128's data will land first and is more actionable. Specifically:

- BC-128 produces signal within 1-2 GRs (≈ 1-2 weeks).
- RFC-016's backfill produces signal only after the read-and-classify pass is complete.
- The defect classes I sketched (JSONB drift, dep resolution, venv divergence) are guesses. BC-128's corpus will reveal whether project-level defects actually cluster the same way model-level failures do, or whether reality groups differently.

Open this RFC for implementation only after: BC-128 has been live for 3+ GRs **and** BC-126's analysis is complete. At that point the question "do we organize breadcrumbs by class?" can be answered against measured cluster structure rather than intuition.

The migration estimate below ("≈ 2 hours of reading") is also revised — reading 125 BCs at ~1 minute each is 2 hours *before* writing any CLASS files. Realistic backfill cost: half a day, not 2 hours. Worth knowing before scheduling.

---

## Problem

At BC-125 the per-defect breadcrumb model is showing strain.

Concrete symptoms from the existing corpus:

- BC-064, BC-076, BC-092, BC-096-class were all "JSONB-safe validation reached one more entry point" — same shape, four breadcrumbs.
- BC-072, BC-077, BC-084 are all "dependency module name resolution edge case" — same shape, three breadcrumbs (and BC-120 is a fourth in spirit).
- BC-079, BC-080, BC-082, BC-083 (substrate, but the pattern is identical) are all "in-memory backend skipped a validation the postgres backend performed" — same shape.

Each defect was real and the fixes were correct. But the *retrieval cost* is now nonlinear: a reviewer scanning the open table cannot tell which BCs are instances of a known class vs. fresh-shape problems. The README index is becoming a flat log, not a taxonomy. v1 hit this around BC-200 and the response was "stop reading them" — which is how v1 ended up rebuilding the import manifest system three times.

This is process debt, not product debt. The product is fine. The way we record problems is what's bending.

## Proposed design

Introduce **defect classes** as a first-class breadcrumb kind, sitting alongside individual BCs and RFCs.

A defect class is a file (`breadcrumbs/CLASS-NNN-<slug>.md`) that captures:

1. The *shape* of the defect (one sentence, copy-pasteable).
2. The *systemic cause* (one paragraph — what about the substrate/pipeline/prompt makes this defect class possible).
3. The *systemic fix* (the design change that would eliminate the class, vs. patching instances).
4. A table of *instances*: the individual BC numbers, what entry point they hit, when they were filed.
5. A *trigger condition* for the systemic fix: how many instances or what severity pattern justifies promoting from "patch instances" to "fix the class."

### File layout

```
breadcrumbs/
  CLASS-001-jsonb-validation-entry-point-drift.md      # NEW
  CLASS-002-dependency-module-name-resolution.md       # NEW
  CLASS-003-inmemory-postgres-validation-divergence.md # NEW (substrate-side)
  126-...
  RFC-016-defect-class-taxonomy.md
```

CLASS files use the same frontmatter schema as BCs/RFCs with `kind: defect-class`.

### How filing changes

The filing rule becomes:

> Before filing a new BC, scan `breadcrumbs/CLASS-*.md` instances tables. If the defect matches an existing class, file the BC normally **and** append a row to the class's instances table. If it does not match, file the BC. If you have just filed the 3rd instance of an unclassified shape, file a CLASS-NNN file before closing the session.

The threshold of 3 is deliberate: 1 is an incident, 2 is a coincidence, 3 is a pattern.

### What CLASS files are NOT

- Not a replacement for individual BCs. Each instance still gets its own BC with its own fix.
- Not RFCs. RFCs are forward-looking proposals; CLASS files are backward-looking pattern recognition that *may* spawn an RFC for the systemic fix.
- Not severity-rated as a single number. The class severity is the **max** of its instances. A class with one critical instance is a critical class even if the other four are low.
- Not auto-generated. The whole point is human pattern recognition.

### Promotion rule

When a CLASS file accumulates ≥ 5 instances OR contains ≥ 2 high/critical instances, the next reviewer must either:

(a) File an RFC proposing the systemic fix and link it from the CLASS file, or

(b) Document in the CLASS file why a systemic fix is **not** worth pursuing (e.g., "instances are bounded; cost of class-level fix exceeds patching cost").

Option (b) is fine and often correct. The point is forcing a decision, not forcing a build.

## Migration plan

One-time backfill (≈ 2 hours of reading):

1. Read every resolved BC from BC-001 through BC-125. Tag each with a candidate class label or "singleton."
2. Any class label with ≥ 3 members becomes a CLASS-NNN file. Initial classes I expect to fall out:
   - CLASS-001: JSONB / contract validation entry-point drift (substrate)
   - CLASS-002: Dependency module name resolution (sf2 BC-072/077/084/120)
   - CLASS-003: Gate vs project venv tool resolution (sf2 BC-115/121)
   - CLASS-004: Channel output extraction edge cases (sf2 various)
   - CLASS-005: Inner gate ↔ outer gate ruleset divergence (sf2 BC-122/123/124-area)
3. The README's Open table gains a `class` column for any BC that maps to one.
4. The README's Resolved table is left alone — backfilling 121 rows is not worth it. The CLASS files reference the instances by number; the table doesn't need to.

Estimated 5-8 CLASS files at backfill time. I'd be surprised if it's > 10.

## Trade-offs

**Cost:** Extra discipline at filing time. Three minutes to check CLASS-*.md instances tables before filing. Compounding: this only pays off if reviewers actually use it.

**Risk: ceremony creep.** The exact failure mode v1 hit. Mitigation: CLASS files have a hard 1-page length limit. If a CLASS file grows past one screen of markdown, it should become an RFC for the systemic fix or be split.

**Risk: forced classification.** Not every defect cleanly belongs to a class. The escape hatch is "singleton" — fine to leave a BC unclassified. The 3-instance threshold prevents pre-mature class creation.

**Risk: classes drift from reality.** A CLASS file written in May 2026 may describe a substrate that no longer exists by August. Mitigation: when an RFC implementing a systemic fix lands, its CLASS file gains a "resolved" frontmatter status and moves to `breadcrumbs/resolved/`. Future instances of the same shape filed against the *new* substrate get a fresh CLASS file. Don't try to maintain one file across substrate generations.

## What this is for

Two concrete things, both visible at session start:

1. **Reviewer onboarding.** A new session reads `breadcrumbs/CLASS-*.md` (5-10 files) and gets the pattern-level picture in 15 minutes. Today the same understanding requires reading ~30 BCs across multiple resolved/ subdirectories.

2. **Where to spend next.** The class with the most recent additions is the loudest signal of "this is where the next RFC should go." This is the same logic as defect taxonomy on model-attempt failures (see BC-128) but operating at the project-defect level rather than the model-output level.

## Out of scope

- Auto-classification of historical BCs by tags or NLP. Manual judgment, period.
- Cross-repo class files (sf2 and substrate stay separate). Each repo's CLASS files reference only that repo's BCs.
- Tooling for "find me all instances of class X." `grep` is fine. Build tooling only if `grep` becomes inadequate.
- Versioned CLASS files. When the substrate generation changes, the old CLASS files resolve; new ones are created. Don't try to migrate.

## Validation criteria

- After 4 weeks: CLASS file count is between 4 and 12. (Less means we didn't backfill; more means we're over-classifying.)
- After 8 weeks: at least one CLASS file has triggered an RFC. (If none, the rule isn't producing decisions — re-evaluate the threshold.)
- After 8 weeks: BC filing-rate has not dropped. (If reviewers are skipping filing to avoid the CLASS check, the discipline cost is too high.)
- A new contributor session can describe the 3 most-active defect classes after reading only `breadcrumbs/CLASS-*.md`.

## Phase placement

Phase 3 (current). This is process work, not product work — no model invocations, no pipeline changes, no spec changes. Lands as a single PR with the backfill and the README rewrite.

## Suggested PR shape

1. Add `kind: defect-class` to schema in `breadcrumbs/README.md`.
2. Add the filing rule and promotion rule to `breadcrumbs/README.md`.
3. Create initial 5-8 `CLASS-NNN-<slug>.md` files (the backfill).
4. Update `breadcrumbs/README.md` Open table with a `class` column.
5. Update `AGENTS.md` with one paragraph pointing new sessions at `CLASS-*.md` before they start filing.

No code changes, no test changes.
