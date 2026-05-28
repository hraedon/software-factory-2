# Golden Run 006a — cert-watch-mini adversarial run

**Date:** 2026-05-09
**Config:** `golden-run-006a-config.yaml` (claude-code channel, Sonnet)
**Fixtures:** `tests/fixtures/cert-watch-mini/` (3 interface specs)
**Pre-built venv:** `/tmp/sf2-gr006a/.venv` with `cryptography>=42.0`
**Project:** `sf2_gr006a`

## Results Summary

| Metric | Value |
|---|---|
| Total work-items | 7 |
| Locked | 5 (71%) |
| Escalated (cannot_proceed) | 2 (29%) |
| Interface spec lock rate | 3/3 = 100% |
| Test suite lock rate | 1/3 = 33% |
| Implementation lock rate | 1/3 = 33% |
| Unknown gate names | 0 |
| Telemetry verify | PASS |

## Detailed Item States

| Work Item | Type | State | Notes |
|---|---|---|---|
| `08a309cb` | interface_spec | **locked** | wi_certificate_model |
| `2079e778` | interface_spec | **locked** | wi_fr03_file_upload |
| `ad21cfa8` | interface_spec | **locked** | wi_fr02_tls_scan |
| `2987ae78` | test_suite | **locked** | for wi_certificate_model |
| `32428732` | test_suite | **cannot_proceed** | wi_fr03_file_upload — test_suite_collect fails |
| `da22d233` | test_suite | **cannot_proceed** | wi_fr02_tls_scan — test_suite_collect fails |
| `aaf5dc89` | implementation | **locked** | for wi_certificate_model |

## Root Cause Analysis

**Primary failure mode:** Cross-module import resolution in `test_suite_collect` gate.

Both FR-02 and FR-03 test_suites import `Certificate` from `certificate_model`:
```python
from certificate_model import Certificate
```

The gate's `_run_pytest_collect` only copies the direct `interface.pyi` → `interface.py` into the temp directory. It does NOT copy the `certificate_model` module, so pytest collection fails with:
```
ERROR collecting artifact.py
ModuleNotFoundError: No module named 'certificate_model'
```

This is a known gap: the gate temp directory setup handles the single `interface_ref` but not transitive/cross-module dependencies. The certificate_model interface_spec is referenced as a dependency in both FR-02 and FR-03 specs, but the scheduler only propagates the direct `interface_ref` into downstream work-items; it doesn't track the full dependency graph.

## Telemetry Observations

- `event_schema_unknown_fields` warning on `custom_fields_update`: regista automatically merges `custom_fields` into event payload. This is cosmetic and doesn't affect telemetry correctness.
- Mean duration for test_author: 10.5s (certificate_model), 17.9s (failed collects for FR-02/FR-03)
- Mean duration for interface_architect: 8.2s
- Mean duration for implementer: 4.2s

## Phase 2 Decision

Per `plans/phase2-close-and-phase3-prep.md` §2.3:

> | `test_gr006a_meets_phase2_exit_threshold` fails (<40% impl) | Pause Phase 3; root-cause |

**Implementation lock rate: 33% (< 40%). Decision: PAUSE Phase 3.**

The root cause is the cross-module import resolution bug. Before Phase 3 can begin, this must be fixed:

1. Scheduler must propagate full dependency chain (not just `interface_ref`) into implementation work-items
2. Gate's `_run_pytest_collect` and `_run_pytest` must copy ALL dependency `.pyi` files into the temp directory, not just the direct interface
3. Alternatively: the test_author prompt must be instructed not to import from modules outside the direct interface (but this is a prompt-level fix, not structural)

## Files

- Results: `tests/fixtures/golden-run-006a/telemetry.json`, `artifacts.json`
- Config: `golden-run-006a-config.yaml`
- Log: this file
