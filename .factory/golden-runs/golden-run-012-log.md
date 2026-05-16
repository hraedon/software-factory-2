# Golden Run 012 — Cert-Watch Full Fixture, Dependency Ordering (BC-077 filed)

**Date:** 2026-05-11
**Config:** `golden-run-012-config.yaml`
**Channel:** opencode (kimi-k2p6-turbo via Fireworks)
**Fixture:** `tests/fixtures/cert-watch/` (8 specs, full DAG)
**Project:** `sf2_golden_012`

## Purpose

Incorporate Opus/GLM feedback into cert-watch fixture (AC enforcement, non-FR module `cert_chain_library`, dep ordering). Execute against updated fixture.

## Results Summary

| Stage | Total | Locked | Cannot proceed | Lock rate |
|---|---|---|---|---|
| interface_spec | 8 | 8 | 0 | 100% |
| test_suite | 8 | 3 | 5 | 37.5% |
| implementation | 3 | 3 | 0 | 100% |
| **Total** | **19** | **14** | **5** | **73%** |

**Wall clock:** 26.3 min.

## Per-module detail

| Module | Interface spec | Test suite | Implementation |
|---|---|---|---|
| certificate_model | locked | locked | locked |
| cert_chain_library | locked | **cannot_proceed** | — |
| database_layer | locked | **cannot_proceed** | — |
| fr01_dashboard | locked | **cannot_proceed** | — |
| fr02_tls_scan | locked | **cannot_proceed** | — |
| fr03_upload | locked | **cannot_proceed** | — |
| fr04_alerts | locked | locked | locked |
| fr05_scheduler | locked | locked | locked |

## Root cause: BC-077 — Runner lacks dependency ordering

`certificate_model` (root dependency) was the **last** interface_spec to be processed. All 5 downstream test_suites failed because their dependency's interface spec wasn't locked when the gate tried to resolve imports.

**5 escalated test_suites (all `test_suite_collect` ImportError):**
- cert_chain_library, database_layer, fr02_tls_scan, fr04_alerts, fr01_dashboard

The runner claims items in database query order without respecting dependency topology.

## Non-FR module finding

`cert_chain_library` was handled correctly by all pipeline components. Failed for the same root cause as other modules (missing certificate_model), not because of its non-FR status.

## AC enforcement

Could not be validated — tests failed at collection before assertions could run. Requires BC-077 fix first.

## Telemetry

Telemetry verify: passed (0 unknown gates, 0 orphans, 0 confounding).

## Breadcrumbs filed

- **BC-077:** Runner processes interface_specs without dependency ordering. Proposed fix: scheduler should defer test_suite creation until all dependency interface_specs are locked.

## Changes since prior run

- Added `wi_cert_chain_library.md` — non-FR utility module with 4 ACs
- AC enforcement for runtime dep function calls in fr02, fr04, database_layer
- fr04_alerts wired to certificate_model + database_layer (3rd diamond consumer)
- fr02/fr03 also depend on cert_chain_library

(End of file)
