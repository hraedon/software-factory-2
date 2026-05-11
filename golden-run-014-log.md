# Golden Run 014 — Full Cert-Watch DAG (BC-084 fix)

**Date:** 2026-05-11
**Config:** `golden-run-014-config.yaml`
**Fixture:** `tests/fixtures/cert-watch/` (8 specs, full DAG)
**Channel:** opencode (kimi-k2p6-turbo via Fireworks)
**Wall clock:** ~33 min (05:37 – 06:10 UTC)

## Results

| Stage | Total | Locked | Cannot proceed | Lock rate |
|---|---|---|---|---|
| interface_spec | 8 | 8 | 0 | 100% |
| test_suite | 8 | 6 | 2 | 75% |
| implementation | 6 | 6 | 0 | 100% |
| **Total** | **22** | **20** | **2** | **91%** |

### Per-module detail

| Module | Interface spec | Test suite | Implementation |
|---|---|---|---|
| certificate_model | locked | locked | locked |
| cert_chain_library | locked | locked | locked |
| database_layer | locked | locked | locked |
| fr01_dashboard | locked | **cannot_proceed** | — |
| fr02_tls_scan | locked | locked | locked |
| fr03_upload | locked | locked | locked |
| fr04_alerts | locked | **cannot_proceed** | — |
| fr05_scheduler | locked | locked | locked |

Only 2 test_suites escalated (vs 5 in GR-013). Both failures are model quality issues, not pipeline bugs:

- **fr01_dashboard**: `ImportError while importing artifact.py` — model-generated test suite could not import its own artifact
- **fr04_alerts**: `from interface import AlertConfig` → `@dataclass(frozen=True)` error in the model-generated interface — invalid dataclass usage

## BC-084 validation — PASSED

The `module_name` custom field is now the single source of truth for module name derivation. The `populate_work_items.py` script stores `label.removeprefix("wi_")` as `CUSTOM_FIELD_MODULE_NAME` on every interface_spec work item. `resolve_dep_artifacts()` reads `module_name` from the dependency's custom fields first, falling back to `_extract_module_name_from_spec()` only when no custom field exists.

Module name derivation comparison:

| Fixture name | GR-013 (spec-title regex) | GR-014 (custom field) | Match? |
|---|---|---|---|
| certificate_model | certificate_model__cert_parser_ | certificate_model | Yes |
| cert_chain_library | certificate_chain_library | cert_chain_library | Yes |
| database_layer | database_layer | database_layer | Yes |
| fr01_dashboard | fr_01_dashboard | fr01_dashboard | Yes |
| fr02_tls_scan | fr_02_tls_scanning | fr02_tls_scan | Yes |
| fr03_upload | fr_03_certificate_upload | fr03_upload | Yes |
| fr04_alerts | fr_04_email_alerts | fr04_alerts | Yes |
| fr05_scheduler | fr_05_daily_scheduler | fr05_scheduler | Yes |

Every module name now matches its fixture file stem. The 5 test_suites that escalated in GR-013 due to `ImportError` from mangled module names all pass the collect gate in GR-014.

## Inner gate validation (BC-075/BC-079/BC-082)

- `68d7d160` (certificate_model impl): inner gate passed retry 0
- `4f875c63` (database_layer impl): inner gate passed retry 0
- `ac56d910` (fr02_tls_scan impl): inner gate passed retry 0
- `1fb31764` (cert_chain_library impl): inner gate passed retry 0
- `a2829ebd` (fr05_scheduler impl): inner gate **failed** retry 0 (E501 Line too long), passed retry 1
- `0b7a1808` (fr03_upload impl): inner gate **failed** retry 0 (E501 Line too long), passed retry 1

BC-079 (inner gate catches tool failures): validated.
BC-082 (ruff format + check): validated — line-too-long caught and auto-formatted on retry.
BC-046 (resume guard): validated — `skipping_resume_due_to_prior_gate_fail` logged for 3 test_suites that had prior gate failures.

## Telemetry verification

```
verify_passed: True
unknown_gate_name_count: 0
unknown_gate_name_rate: 0.0000
orphan_submit_count: 0
unmatched_gate_count: 0
confounding_warning_count: 0
```

Telemetry: 24 items evaluated, 0% first-attempt pass, 83% overall pass.

## Comparison with GR-013

| Metric | GR-013 | GR-014 | Delta |
|---|---|---|---|
| Interface spec lock rate | 100% (8/8) | 100% (8/8) | — |
| Test suite lock rate | 37.5% (3/8) | 75% (6/8) | **+37.5pp** |
| Implementation lock rate | 100% (3/3) | 100% (6/6) | — |
| Overall lock rate | 73% (14/19) | 91% (20/22) | **+18pp** |
| Root cause of escalations | Module name mangling (BC-084) | Model quality (2 items) | Different |
| Telemetry verify | passed | passed | — |

GR-014 validates the BC-084 fix. Test suite lock rate doubled from 37.5% to 75%. The 2 remaining escalations are model quality issues (invalid dataclass usage, import error in model-generated code), not pipeline bugs.

## Changes since GR-013

- **BC-084 resolved:** Added `CUSTOM_FIELD_MODULE_NAME` constant; `populate_work_items.py` derives module name from fixture label (`label.removeprefix("wi_")`) and stores as custom field; `resolve_dep_artifacts()` reads `module_name` from custom fields first, falls back to spec-title regex; `module_name` field added to all three work item types in `phase2.yaml` and `phase1.yaml`; 3 new tests in `test_cross_module_deps.py`
- **Duplicate `import re`** removed from `populate_work_items.py`