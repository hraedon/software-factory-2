---
number: "077"
title: Runner processes interface_specs without dependency ordering — root deps processed last, cascading test_suite ImportErrors
severity: high
status: implemented
kind: bug
author: opencode-glm-5.1
date: "2026-05-11"
tags: [runner, dependency, scheduler, cert-watch, stage-5]
related: ["076", "074"]
---

## Problem

When multiple interface_spec work items exist with dependency relationships, the runner claims and processes them in whatever order the database query returns them — without respecting the dependency graph. If a root dependency (e.g., `certificate_model`) is processed after its dependents, downstream test_suites fail with ImportError during pytest collection because the dependency's interface spec artifact isn't available for the gate's `copy_dependency_pyis`.

## Evidence

- GR-012 (cert-watch full fixture, Kimi via Fireworks, opencode channel):
  - `certificate_model` (root dependency, no deps) was the last interface_spec to be processed — claimed at attempt 2, locked at ~23:01 (22 min into the run).
  - All 5 downstream test_suites that depend on `certificate_model` escalated to `cannot_proceed` at the `test_suite_collect` gate with ImportError:
    - `cert_chain_library`: `from interface import extract_chain` — interface.py has `from certificate_model import Certificate` but `certificate_model` module doesn't exist in temp dir
    - `database_layer`: `from interface import CertificateRepository` — same root cause
    - `fr02_tls_scan`: `from interface import ScannedEntry, ScanError, scan_host`
    - `fr04_alerts`: `from interface import AlertConfig` — also had a dataclass error
    - `fr01_dashboard`: `from interface import dashboard, Request, TemplateResponse`
  - Only 3 test_suites locked: `certificate_model` (no deps), `fr03_upload` (first to lock before deps mattered), `fr05_scheduler` (depends on fr02/fr04, not certificate_model directly).
  - 3/3 implementations locked (of the locked test_suites).
  - Wall clock: 26.3 min.

- The runner's `worker_loop` queries `STATE_NEW` items and claims the first one from the result set, regardless of dependency topology. There is no priority or ordering mechanism for root dependencies.

## Impact

This makes the BC-076 fix vacuously correct for any fixture with transitive dependencies — the downstream tests never reach the runtime dep-call enforcement because they fail at collection first. The AC enforcement changes from the Opus/GLM feedback cannot be validated until this ordering issue is fixed.

## Proposed fix

**Option A: Topological ordering in runner** — When querying for interface_specs in `new` state, sort by dependency depth (leaf-first) so root dependencies are processed before dependents.

**Option B: Scheduler defers test_suite creation** — Only create a test_suite when all of its interface_spec's dependencies have locked interface specs. Prevents the gate from seeing test_suites whose deps aren't ready.

**Option C: Gate skips test_suites with unready deps** — In `_run_pytest_collect`, check if all dependency interface_specs are locked before running collection. Return a "skip" result instead of gate_fail.

Option B is the most architecturally honest — the scheduler already knows the dependency graph via `CUSTOM_FIELD_DEPENDENCY_REFS`. Deferring downstream creation until deps are ready prevents wasting model budget on items that will inevitably fail.

## Non-FR module finding

The `cert_chain_library` (non-FR utility module) was handled correctly by the pipeline machinery — populate, scheduler, runner, and gate all treated it identically to FR-driven modules. Its test_suite failed for the same root cause as the others (certificate_model not locked), not because of its non-FR status. The pipeline tolerates non-FR work-items.
