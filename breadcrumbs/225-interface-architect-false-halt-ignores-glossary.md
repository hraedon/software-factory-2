---
number: "225"
title: "interface_architect halts on FR-local type underspecification without consulting the spec glossary that defines the missing structure"
severity: low
status: implemented
kind: bug
author: claude-opus (review session)
date: "2026-05-29"
tags: [interface-architect, stage-1, decomposer, epistemic-calibration]
related: ["224", "RFC-039"]
---

## Symptom

In GR-048, FR-03 stats_reader went claim → `cannot_proceed` at the `interface_spec` stage in 28s. The interface_architect (K2) refused to proceed with:

> "Spec is ambiguous regarding the structure of individual hit entries in the hits array … FR-03 says 'return … up to 10 recent hits' but does not define the fields or types of individual hit entries … impossible to define a precise type … without inventing fields."
> (`/tmp/sf2-golden-048/d1c9f275-.../attempt-0001/cannot_proceed.json`)

But the url-shortener spec's **glossary defines a hit**: "A recorded access … Each hit stores timestamp, source IP, and user-agent." The structure the architect said was missing is present in the spec — just in the glossary, not inline in FR-03/AC-05.

## Why it matters (and why only low)

The halt is *defensible* — refusing to invent fields is the epistemic-honesty behavior RFC-030 wants, and a false halt is far safer than the confident-wrong stub failures the same run produced (BC-224). Low severity because the failure mode is conservative (it blocks, it doesn't ship wrong code). But it is still a real defect: the agent did not use available in-spec context (the glossary) to resolve an FR-local ambiguity, so it halted on something resolvable.

It is also the **inverse half of the BC-224 finding**: the same run shows the pipeline confidently wrong on a wholly-unmet HTTP contract (no FastAPI at all) yet halting on a small, glossary-resolvable gap. The epistemic calibration is anchored to surface readability (precise types) rather than to behavioral conformance — uncertainty fires on the wrong things.

## Proposed fix (directions)

- Interface-stage prompt: before declaring an AC/FR underspecified, the architect must check whether the spec's glossary / data / business-rules sections define the referenced entity, and resolve from there.
- May be partly subsumed by RFC-039: a deliverable-altitude unit (a `stats` vertical slice that owns the hit record) would carry the glossary-defined hit structure in context rather than seeing FR-03 in isolation.

## Fix

Updated `src/factory/prompts/interface_architect.md` structured-failure section: before declaring an AC or FR underspecified, the architect must explicitly (1) search the glossary for referenced entity definitions, (2) check data/business_rules/error_handling sections, and (3) only issue `cannot_proceed` if all sources have been exhausted and a genuine ambiguity remains.

## Why this isn't the previous fix recurring

N/A — first instance of this defect shape (interface-stage context-utilization gap: available spec context not consulted before halting).
