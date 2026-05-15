---
number: "RFC-026"
title: "Principal review surface — the pipeline needs an artifact bundle format and feedback intake"
severity: high
status: proposed
kind: design
author: agent
date: "2026-05-15"
tags: [rfc, stage-10, principal-review, artifact-delivery]
related: ["RFC-019", "RFC-021"]
---

## Summary

Stage 10 (Principal Review) is the only human gate in the pipeline (spec §4 lines 85-88). When a DAG completes (all items locked or terminal), the principal must receive an artifact bundle that answers "does the running software do what was asked?" and provide a feedback path: "Yes → ship. No → feedback as new/revised AC, re-run affected stages."

Neither the artifact bundle format nor the feedback intake mechanism has a design. RFC-019 covers output delivery (mechanism) but not bundle *content*. RFC-021 covers spec mutation (how revised ACs update the spec) but not the principal's interaction surface.

## Design questions

1. **What's in the bundle?** At minimum: assembled source tree, integration test results, outcome verification verdict, per-work-item lock state, per-work-item artifacts (interface .pyi, test .py, implementation .py). Optionally: telemetry report, failure analysis for cannot_proceed items, diff from spec.
2. **How is the bundle presented?** A tarball? A directory? A CLI command (`factory report --project NNN`)? The principal is a systems architect, not a developer — the format should minimize friction.
3. **How does feedback enter the pipeline?** Does the principal edit the spec and re-run? Does a CLI command accept "AC-02: the error case returns None instead of ErrorCode.NOT_FOUND"? Is there a diff format for revised ACs?
4. **How does re-run work?** Does it reset the entire DAG or only affected stages? If an AC changes in one module, should the integration for unrelated modules be preserved?

## Current state

- `report.py` exists but hardcodes `workflow_version=1` (BC-045 — acknowledged but not fixed for Phase 5 workflows).
- Telemetry (`run_telemetry_report`) produces per-role pass-rate tables but no per-work-item artifact summary.
- The workspace at `/tmp/sf2-golden-NNN/` contains raw artifacts by work-item-ID, but there's no index or manifest.

## Phase needed

Phase 6 (first real workload). Until there's a real workload, the principal has no reason to review artifacts. Phase 5 is synthetic-fixture validation where the principal already knows what the output should be.
