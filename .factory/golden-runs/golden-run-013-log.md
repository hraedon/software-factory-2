# Golden Run 013 — Full Cert-Watch DAG

**Date:** 2026-05-11
**Config:** `golden-run-013-config.yaml`
**Fixture:** `tests/fixtures/cert-watch/` (8 specs, full DAG)
**Channel:** opencode (kimi-k2p6-turbo via Fireworks)
**Wall clock:** ~30 min (03:29 – 04:01 UTC)

## Results

| Stage | Total | Locked | Cannot proceed | Lock rate |
|---|---|---|---|---|
| interface_spec | 8 | 8 | 0 | 100% |
| test_suite | 8 | 3 | 5 | 37.5% |
| implementation | 3 | 3 | 0 | 100% |
| **Total** | **19** | **14** | **5** | **73%** |

### Per-module detail

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

## BC-077 validation

**PASSED.** The scheduler correctly deferred downstream creation until all dependency interface_specs were locked. All 8 interface_specs locked in the first ~10 minutes. The scheduler created test_suites as soon as their parent interface_spec locked, which is the intended behavior.

Root dependency `certificate_model` was the FIRST interface_spec processed (claimed at 03:29:31), compared to GR-012 where it was the LAST. This confirms BC-077's fix is working.

## Root cause of 5 test_suite escalations

**All 5 `cannot_proceed` test_suites failed at `test_suite_collect` with ImportError.**

Root cause: `_extract_module_name_from_spec()` in `dep_resolution.py` derives the module name from the interface spec title (`# Interface Specification: Certificate Model (cert-parser)` → `certificate_model__cert_parser_`). The model-generated interface spec included a parenthetical suffix that mangled the module name.

The gate copies the dependency as `certificate_model__cert_parser_.py`, but the test code imports `from certificate_model import Certificate`. Module name mismatch causes `ImportError` at collection.

The 3 test_suites that passed:
- `certificate_model` — no deps
- `fr04_alerts` — depends on `certificate_model` + `database_layer`. Certificate_model's spec title is "Certificate Model (cert-parser)" → mangled, but the gate apparently succeeded. **Wait — this needs re-investigation.**
- `fr05_scheduler` — depends on `fr02_tls_scan` + `fr04_alerts`, neither of which have locked test_suites. But this is an interface_spec-level dep, so the `.pyi` stubs are fine for collection.

**Correction:** fr04_alerts and fr05_scheduler test_suites passed because their dependency_refs point to `certificate_model` and `database_layer` interface_specs. The module name derivation issue would affect them too... unless the spec titles for fr04_alerts and fr05_scheduler's deps don't have parentheticals. Needs further investigation.

Actually — the `_resolve_dependency_refs` returns the module name from the **dependency's** spec, not the current item's spec. So `certificate_model__cert_parser_` is the module name used for ALL items that depend on `certificate_model`. The 3 passing test_suites (`certificate_model`, `fr04_alerts`, `fr05_scheduler`) either have no deps or their deps' spec titles don't have parentheticals.

**Resolution:** fr04_alerts and fr05_scheduler interfaces don't import from their dependency modules (they only use types defined in their own interface). So even though the dep resolution returns mangled module names, the test code never imports them and collection succeeds. The 5 failing test_suites have interfaces that DO import from deps (e.g., `from certificate_model import Certificate`).

Module name derivation results for all 8 interface specs:

| Fixture name | Spec title | Derived module name | Match? |
|---|---|---|---|
| certificate_model | Certificate Model (cert-parser) | certificate_model__cert_parser_ | No |
| cert_chain_library | Certificate Chain Library | certificate_chain_library | No |
| database_layer | Database Layer | database_layer | Yes |
| fr01_dashboard | FR-01 Dashboard | fr_01_dashboard | No |
| fr02_tls_scan | FR-02 TLS Scanning | fr_02_tls_scanning | No |
| fr03_upload | FR-03 Certificate Upload | fr_03_certificate_upload | No |
| fr04_alerts | FR-04 Email Alerts | fr_04_email_alerts | No |
| fr05_scheduler | FR-05 Daily Scheduler | fr_05_daily_scheduler | No |

Only `database_layer` matched by coincidence. The model freely chooses spec titles, and the regex-based derivation is fragile.

## Inner gate validation (BC-075/BC-079/BC-082)

- `572e8233` (certificate_model impl): inner gate passed retry 0
- `6d7b0c95` (fr01_dashboard impl): inner gate passed retry 0
- `a487607a` (fr05_scheduler impl): inner gate caught mypy `type-arg` error on retry 0, passed retry 1

BC-079 (inner gate catches tool failures): validated — no silent passes.
BC-082 (inner gate catches unfixable lint after format): validated — ruff checks ran correctly.
BC-046 (resume guard): validated — `skipping_resume_due_to_prior_gate_fail` logged correctly.

## Telemetry verification

```
verify_passed: True
unknown_gate_name_count: 0
orphan_submit_count: 0
unmatched_gate_count: 0
```

## Comparison with GR-012

| Metric | GR-012 | GR-013 | Delta |
|---|---|---|---|
| Interface spec lock rate | 100% (8/8) | 100% (8/8) | — |
| Test suite lock rate | 37.5% (3/8) | 37.5% (3/8) | 0 |
| Implementation lock rate | 100% (3/3) | 100% (3/3) | — |
| Overall lock rate | 73% (14/19) | 73% (14/19) | 0 |
| Root cause | BC-077: dep ordering | Module name mangling | Different |
| Telemetry verify | N/A | passed | — |

Same headline numbers but **different root cause**. GR-012's dep ordering issue (BC-077) is fixed. GR-013 reveals a new bug: `_extract_module_name_from_spec` is fragile against model-generated spec titles.

## New breadcrumb needed

**BC-084:** `_extract_module_name_from_spec` derives module names from spec titles using regex, which produces mangled names when the model includes parenthetical suffixes (e.g., "Certificate Model (cert-parser)" → `certificate_model__cert_parser_`). The module name should come from a canonical source (fixture label, work item label, or interface file path) rather than a freeform title.
