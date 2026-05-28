# Golden Run 001 — Measurement Log

**Date:** 2026-05-06
**Config:** `golden-run-001-config.yaml`
**Workspace Root:** `/tmp/sf2-golden-001`

---

## Phase A — Pre-flight (fixing allowed)

### A1: report.py adversarial check fix
- **Status:** COMPLETE
- **Change:** Replaced `cannot_proceed_count > 0` (any item in cannot_proceed) with
  explicit filter: `by_shape["adversarial"]` and assert all adversarial items are in
  `cannot_proceed`.
- **Cleanup:** Removed unused `cannot_proceed_count` variable.

### A2: Raw stdout capture
- **Status:** COMPLETE
- **Change:** `claude_code_channel.py` now writes `result.stdout` to
  `outputs_dir/raw_stdout.txt` before extraction. Located at line ~107:
  ```python
  raw_path = outputs_dir / "raw_stdout.txt"
  raw_path.write_text(output_text)
  ```

### A3: Claude smoke test
- **Status:** COMPLETE
- **Command:** `cat tests/fixtures/primary-spec/01-acquire_claim.md | claude --print --output-format text --max-turns 1`
  - **Result:** Claude asked "What would you like me to do with this spec?" — raw spec piping does not trigger role behavior.
- **Full prompt test:** Rendered `render_prompt(ctx)` with `interface_architect.md` role prompt + spec section + AC-06.
  - **Result:** Single fenced `python` block, no preamble, no postscript.
  - **Extractor verified:** `_extract_artifact_from_output()` correctly parses the output.
- **Output at:** `/tmp/claude-smoke.txt`

### A4: Workspace root
- **Status:** COMPLETE
- **Workspace root:** `/tmp/sf2-golden-001` (created)
- **Config file:** `golden-run-001-config.yaml` sets `workspace_root: /tmp/sf2-golden-001`
- Runner at `runner.py:122` uses `Path(config.workspace_root)` — unambiguous absolute path.

### A5: Run-log created
- **Status:** COMPLETE
- **File:** `golden-run-001-log.md` (this file)

---

## Test Baseline

```
61 passed, 1 skipped, 6 deselected in 0.32s
ruff: All checks passed!
```

---

## Phase B — Dry Run of One

### B1: Population
- **Timestamp:** 2026-05-06 23:08
- **Command:** `.venv/bin/python3 populate_work_items.py --project sf2_dryrun --reset --only 01`
- **Work-item:** `f40967fa-e87e-487d-aae9-85b528a21f2f` (pure-interface, AC-06)
- **Status:** SUCCESS

### B2: Runner + Gate start
- **Timestamp:** 2026-05-06 23:09:37
- **Commands:**
  - `factory-run --config dry-run-config.yaml`
  - `factory-gate --config dry-run-config.yaml`

### B3: Observation
- **claim acquired:** 23:09:37, attempt 1
- **claim transition (new→in_progress):** 23:09:37 (~0ms)
- **submit transition (in_progress→gating):** 23:09:55 (~18s — Claude processing time)
- **gate acquired:** 23:09:56
- **gate_pass transition (gating→locked):** 23:09:56 (~1s gate eval)
- **Total wall-clock:** ~19 seconds new→locked

### B4: Issues Found and Fixed
1. **Runner missing claim transition** — `acquire_claim` only creates a DB claim row; runner must explicitly call `sub.transition(wi, "claim", actor_id, actor_metadata=...)`. Fixed at runner.py:91.
2. **Context derivation replaced work-item content with factory spec.md** — `derive_context()` had `section_content = spec_content if spec_content is not None else spec_section`, which loaded the factory's own spec.md when `spec_file` was set. Fixed to prefer work-item's `spec_section` custom field.
3. **populate_work_items.py stale API** — `create_work_item()` no longer takes `workflow_version`; returns `tuple[WorkItem, Event]`. Updated.
4. **Regista import conflict** — PyPI `regista` package vs local `/projects/regista`; resolved by installing local editable via `uv pip install -e /projects/regista`.

### B5: Success Baseline
- **State:** locked
- **Attempt:** 1
- **Gate diagnostics:** None (all gates passed)
- **Context hash:** `b59fd13e7eef110b`
- **Claude .pyi produced:**

```python
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Union


@dataclass(frozen=True)
class ClaimAcquired:
    """Successful claim acquisition. Satisfies AC-06."""
    work_item_id: str
    claimant: str
    attempt_number: int
    claimed_at: datetime
    expires_at: datetime
    stole_expired_claim: bool


@dataclass(frozen=True)
class ClaimContested:
    """Rejection: another claimant won the row lock first. Satisfies AC-06."""
    work_item_id: str


@dataclass(frozen=True)
class NotYetEligible:
    """Rejection: work-item's not_before is in the future. Satisfies AC-06."""
    work_item_id: str
    not_before: datetime


ClaimResult = Union[ClaimAcquired, ClaimContested, NotYetEligible]


def acquire_claim(
    work_item_id: str,
    claimant: str,
    now: datetime,
    lease_duration: timedelta,
) -> ClaimResult:
    """Satisfies AC-06."""
    ...
```

- **raw_stdout.txt:** Single fenced `python` block, no preamble, no postscript. Extraction clean.
- **sha256:** `4bf5239d26f39aeea198256fd9657e17fec46f31fddbf1fafe6c48c5db4ef28e`
- **size:** 906 bytes

---

## Phase C — The Measurement

### C1: Full population
- **Timestamp:** 2026-05-06 23:30:25
- **Command:** `.venv/bin/python3 populate_work_items.py --project sf2_golden_001 --reset`
- **Result:** 11 work-items created (01-10 primary + AA adversarial)

### C2: Run start time
- **Start:** 2026-05-06 23:30:25
- **Runner PID:** 1907502, **Gate PID:** 1907503

### C3-C5: Time-series observations

**T+0m (23:30:25) — Start**
- 11 items in `new`

**T+2m (23:32:30) — In progress**
- 4 locked, 1 cannot_proceed, 6 in_progress/being claimed

**T+~3.5m (23:33:45) — Complete**
```
State summary:
  new             :   0
  in_progress     :   0
  gating          :   0
  locked          :  10
  cannot_proceed  :   1

Category breakdown:
  pure-interface      : 3/3 locked (100%)
  error-taxonomy      : 3/3 locked (100%)
  ADT-validation      : 4/4 locked (100%)
  adversarial         : 0/1 locked (0%)

Primary set (>=9/10 locked): 10/10 PASS
Adversarial (cannot_proceed): cannot_proceed
Overall exit criteria met: YES
```

### C6: End time
- **End:** 2026-05-06 23:33:45
- **Total wall-clock:** ~3.5 minutes (11 Claude invocations, ~10-15s each + gate time)
- **Stopped:** `kill` sent to both processes at 23:34

---

## Phase D — Post-Mortem

### D1: Final report

```
10/10 locked, 1/1 adversarial in cannot_proceed
ALL exit criteria PASS
100% first-attempt pass rate on primary set
```

### D2: Adversarial assertion
- **Manual check:** `adversarial item 02582ca0-a444-434b-9e8a-193d18c6dc94 state=cannot_proceed` — PASS
- **Pytest test:** `TestAdversarialItemContract::test_adversarial_item_asserts_cannot_proceed` — skipped (requires test project with adversarial item populated)

### D2.1: Adversarial raw_stdout.txt — what Claude actually emitted

Claude produced a **single fenced JSON block only**. No prose preamble, no half-stub-half-JSON, no chat. The extractor's `_extract_json_from_output()` found the `json` block, parsed valid JSON with `"status": "cannot_proceed"`, and returned early.

This is a strong positive signal: the `interface_architect.md` prompt's structured-failure instruction ("Do NOT also write `artifact.pyi`") is working as intended. Claude spontaneously chose the correct failure path without producing a garbage stub alongside it.

```
```json
{
  "status": "cannot_proceed",
  "reason": "Spec is ambiguous regarding sort order, record schema, and edge-case semantics",
  "gaps": [
    "Sort key is unspecified: AC says 'sort' but does not say by date, amount, category, or a composite...",
    "Sort direction is unspecified: ascending vs descending is not stated...",
    "Record type is unspecified: 'date', 'amount', 'category' are named but their Python types not given...",
    "Return shape is unspecified: whether the function returns a new list, mutates in place, or returns a Result/Error union...",
    "'Edge cases' in TS-ADV-02 is undefined...",
    "Stability is unspecified: whether equal keys must preserve input order...",
    "Failure mode is unspecified: whether bad input raises, returns an Error variant, or is silently dropped..."
  ],
  "would_need": "Concrete clarification of (a) the exact sort key and direction, (b) the input record schema with field types, (c) the return type and whether mutation is allowed, (d) an enumerated list of edge cases with the required behavior for each (...), and (e) stability guarantees for ties."
}
```
```

The full JSON is also preserved at `/tmp/sf2-golden-001/02582ca0-a444-434b-9e8a-193d18c6dc94/attempt-0001/cannot_proceed.json`.

### D3: Semantic spot-check (post hoc — does the gate mask semantic errors?)

**Principle:** `evaluate_interface_spec()` checks file exists, non-empty, valid Python syntax, no implementation bodies, AC references present. All syntactic. None verify the interface is correct against the spec. A .pyi defining `acquire_claim(x: int) -> bool` with `"""Satisfies AC-06."""` would pass the gate just as cleanly as the correct variant-type version.

**Method:** Read the produced .pyi against the fixture spec for one item per shape. Confirm by eye that signatures, ADT shapes, and error taxonomies match what the spec demands.

#### 01-acquire_claim (pure-interface)

Spec demands: single function with typed signature, no enumerated error return. AC-06 requires three outcomes: (1) successful claim, (2) `not_before` rejection, (3) "claim contested" rejection.

Artifact: `AcquireOutcome = Union[ClaimAcquired, ClaimContested, NotYetAvailable]` — all three outcomes present with correct field shapes. `ClaimAcquired` includes `attempt_number` matching "auto-steal increments attempt_number." Function takes `claim_duration_seconds: int` as an explicit parameter (reasonable for a pure-interface contract). **PASS.**

#### 04-verify_event (error-taxonomy)

Spec demands: function centrally including an enumerated error set. AC-15/AC-26 require three rejections (unknown key, revoked key, signature mismatch) plus deprecated-warning path.

Artifact: `ErrorCode` enum has exactly three values: `UNKNOWN_KEY_ID`, `REVOKED_KEY_ID`, `SIGNATURE_MISMATCH`. `VerifyError` contains `actor_id_claim, key_id_claim, event_id` matching spec's "structured log with actor_id_claim, key_id_claim, event_id." `VerifyOk` has `deprecated_key_warning: bool` matching "emit structured warning." Signature takes `canonical_envelope: bytes` matching spec's stored-bytes requirement. **PASS.**

#### 07-drift_report (ADT-validation)

Spec demands: three categories (`replayed_ok`, `replayed_drift`, `halted`), four halt reasons, `warnings` field, aggregate report with counts, one row per work-item.

Artifact: `ReplayCategory` has all three. `HaltReason` has all four (`revoked_key`, `missing_workflow_version`, `unrecognized_transition`, `signature_verification_failed`). `ReplayReportRow` has `halt_reason: Optional[HaltReason]` matching halted-vs-other semantics. `DriftReport` aggregate has `replayed_ok/drift/halted_count`. `warnings: int` matches "count of events skipped during signature verification." **PASS.**

**Verdict:** All three spot-checks pass. Claude produced semantically correct interfaces, not just syntactically valid .pyi files. The gate being syntactic-only did not mask a real problem in this run. The 100% first-attempt pass rate reflects genuine interface quality for this test set.

### D4: Failure taxonomy

**No failures.** All 10 primary items passed first attempt. The adversarial item correctly hit `cannot_proceed`.

### D5: Cluster analysis

All shapes passed at 100%:
- pure-interface: 3/3
- error-taxonomy: 3/3
- ADT-validation: 4/4
- adversarial: correctly in cannot_proceed

### D6: Key observations

1. **Claude produces clean, single-fenced blocks consistently.** No chatty preamble observed in any of 11 invocations.
2. **Extraction is non-issue.** The simple regex in `claude_code_channel.py` works reliably for both `python` and `json` blocks.
3. **Gate is appropriately permissive.** No false negatives on valid .pyi files.
4. **Claude latency:** ~8-19 seconds per invocation (typical for `--max-turns 1`).
5. **Context hash determinism:** Same fixture content produces same context_hash across reruns (b59fd13e for item 01 in both dry run and golden run).
6. **Prompt is effective.** The structured-failure path in `interface_architect.md` works: Claude emitted pure JSON with no stub alongside it for the adversarial item.

### D7: Breadcrumbs filed

| # | Title | Severity | Status |
|---|---|---|---|
| 008 | Test gap — claim transition not asserted in worker loop tests | high | proposed |
| 009 | Context derivation tests should exercise both spec_file paths | high | proposed |

### Bugs fixed during this session

1. **Runner missing `claim` transition** — `acquire_claim()` creates DB claim row but doesn't change state; runner must call `sub.transition(wi, "claim", ...)` explicitly.
2. **Context derivation `spec_content` override** — `derive_context()` replaced work-item `spec_section` with factory-level `spec.md` when `spec_file` was set. Fixed to prefer work-item content.
3. **Actor role idempotency** — `register_actor_role` fails if role already registered; wrapped in try/except.
4. **populate_work_items.py API changes** — `create_work_item()` no longer takes `workflow_version`; returns tuple. Updated.
5. **Regista import conflict** — PyPI vs local regista package; resolved via `uv pip install -e`.
6. **report.py adversarial check** — was checking any item in cannot_proceed, not specifically adversarial items.

### Phase 1 exit criteria verdict

**PASS — 100% first-attempt pass rate, all exit criteria met, semantic spot-checks clean.**

The interface_architect role + Claude channel are ready for Phase 2 expansion.
