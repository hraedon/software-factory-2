---
number: "222"
title: "outcome_e2e gate on web-service workloads is unvalidated — GR-047 escalation with unknown root cause (server lifecycle vs run-and-exit CLI)"
severity: medium
status: proposed
kind: bug
author: claude-opus (review session)
date: "2026-05-29"
tags: [outcome-verification, gate, phase-6, web-service]
related: ["209", "CLASS-008"]
---

## Symptom

GR-047 (first non-CLI workload, url-shortener) had **one `outcome_e2e` gate escalation** and **one orphan submit** at the outcome_verification stage, against an otherwise clean run (100% inner-gate first-pass, 100% review pass). The GR-047 log records the escalation's root cause as unknown: *"The escalation suggests the service didn't start correctly or the e2e test failed."* No forensics were done, and the workspace + logs were cleaned, so the evidence is unrecoverable.

## Why this is a real gap, not noise

Every workload validated to date (cert-watch, log-redact-cli, dep-graph-viewer) is a CLI tool with a **run-and-exit** lifecycle: the outcome verifier invokes the binary, feeds stdin, reads stdout/exit-code, done. A web service has a fundamentally different lifecycle the `outcome_e2e` gate has never had to handle:

- A long-running server process (uvicorn/FastAPI) must be **started, health-probed, exercised over HTTP, then torn down**.
- Port binding, startup race (probe before the server is listening), and process-group teardown are all live concerns that simply do not exist for run-and-exit CLIs.
- A hang or a missing teardown looks like an "escalation" or an "orphan," which is exactly the GR-047 signature.

This means the `outcome_e2e` gate's behavior on server-shaped workloads is **unvalidated**, and the one data point we have is a failure with no root cause.

## Possible CLASS-008 relationship

This may be an instance of CLASS-008 (Gate Subprocess Execution and Environment Handling), which is *stabilized* by RFC-011's unified subprocess layer. If the escalation is a server-startup/teardown handling gap in the outcome gate's subprocess management, it belongs in that class. **Not appending to the CLASS-008 instances table yet** — the root cause is unconfirmed (artifacts deleted). GR-048 (below) should preserve artifacts and pin the cause; if it is a subprocess-lifecycle issue, append the row then.

## Proposed investigation

1. Re-run url-shortener with `--no-cleanup` (this is already planned as GR-048 for the jury question — fold this forensic into the same run).
2. When the `outcome_e2e` item escalates (if it does), inspect the gate subprocess: did the server start? did the probe race the bind? did teardown leak a process?
3. Reproduce the gate command with both `.venv/bin/python` and the workspace `.venv-gate/bin/python` per the BC-174 protocol in AGENTS.md.

## Proposed fix (pending root cause)

If confirmed as a server-lifecycle gap: the outcome verifier needs an explicit "long-running service" mode — start, wait-for-listen with a bounded health-probe loop, run e2e, guaranteed teardown (process-group kill). The CLI run-and-exit path stays the default; the service path is selected by workload shape.

## Update 2026-05-29 — root cause reframed by GR-048 (server-lifecycle hypothesis likely WRONG)

GR-048 re-ran url-shortener with artifacts preserved. Both `outcome_e2e` escalations reproduced (FR-01 link_creator, FR-04 link_lister → `cannot_proceed`). Forensics show the escalations are **not** a subprocess/server-lifecycle handling bug. The deeper cause: **the workers never produced an HTTP service at all** — `grep` for FastAPI/Flask/http.server/WSGI across every artifact returns 0 files, despite the spec deciding FastAPI. `outcome_e2e` is *correctly failing* because there is no runnable service to exercise end-to-end.

So this BC's original hypothesis (uvicorn startup race / process-group teardown) is unproven and probably misattributed. The real gap is upstream (BC-224: the pipeline produces stub/non-HTTP code for HTTP specs and most gates bless it). The latent server-lifecycle concern remains theoretically valid but cannot be assessed until a workload actually produces a server to verify.

**Also note `outcome_e2e` is inconsistent:** it caught FR-01 and FR-04 but PASSED FR-05 error_formatter, which has no HTTP 422 endpoint (BC-224). So even the e2e gate has AC-coverage gaps on error paths. Severity unchanged (medium); status stays proposed; investigate `outcome_e2e` error-path coverage as part of the BC-224 work.

**Systemic direction:** RFC-038 reframes `outcome_e2e` as the right *concept* executed by the wrong *oracle* (LLM rather than deterministic AC-execution). The FR-05 leak is exactly what a deterministic AC-derived acceptance suite (assert `POST /links {url:123}` → 422) would not miss. See RFC-038.

## Why this isn't the previous fix recurring

N/A — first instance of this defect shape (outcome verification of a server-lifecycle workload). Related to BC-209 (the broader "no production-complexity workload validation" gap) and BC-224 (the upstream stub-code root cause). The CLASS-008 association is now doubtful given the reframed root cause.
