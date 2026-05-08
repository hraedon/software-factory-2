---
model: deepseek-v4-pro
datetime: 2026-05-08T23:00 UTC
project: software-factory-2
---

# Session Reflection — 2026-05-08

**Work summary:** Adversarial review of the factory repo and cross-reference with v1 lessons. Filed 15 breadcrumbs (11 from v2 review, 4 actionable from v1 patterns, 5 RFCs from v1 deferred lessons). Updated AGENTS.md, README.md, spec.md from Phase 0/1 to Phase 2 with accurate inventory.

---

## On the project

The factory is in a genuinely good place for Phase 2. The 7-module decomposition is clean — each file has a clear responsibility. Gate, router, scheduler, and runner compose well. The 259-test suite runs in 15 seconds and covers the business logic thoroughly. The three golden runs prove the pipeline shape works end-to-end: 100% interface_spec and test_suite lock rates, with implementation being the only remaining pain point.

The architectural debt that sank v1 (god-function pipeline, memory graph trap, too-broad roles, string constant gravity) is all explicitly avoided by design. Principle 6 ("filling-in roles, not architectural roles") and Principle 8 ("errors loop back to contract revision") directly counter v1's worst failure modes. The fact that the spec explicitly calls out the memory graph avoidance in §9 is a strong signal of institutional learning.

The remaining fragility is documentation staleness. AGENTS.md and README.md were both frozen at Phase 0 while the project advanced through Phases 1 and 2. This is the same pattern that hit v1's docs — and it's the hardest to catch because agents read the authoritative files and trust them. Automated doc generation (RFC-004) would close this gap permanently.

The test_author.md truncation is the most concerning finding. It means every golden run's test suites were produced against a broken prompt. The 100% pass rate suggests the worked example is sufficient for the fixture set, but this is a silent correctness risk that could produce vacuous tests for more complex ACs without anyone noticing.

## On the work done

The adversarial review was systematic. Reading the full codebase, all golden run postmortems, every open breadcrumb, and cross-referencing against v1's lessons produced findings at every severity level. The v1 cross-reference was the most productive part — BC-383 (prompt conflicts causing silent agent paralysis) is directly applicable to v2's BC-050 (interface_architect example contradicts implementer rules). BC-358 (contract enforcement that warns-and-continues) maps directly to gate_process.py's silent-None fallbacks for missing interface_ref.

The doc updates were straightforward. Making AGENTS.md the single source of truth for conventions (default-value rule, RFC convention, make commands) reduces the number of places a new agent needs to look. The Phase 0/1 COMPLETE markers in spec §10 create a clear record of what was validated and what wasn't.

The incidental line-length lint fix in test_opencode_channel.py was caught by `make check` — a good demonstration that the CI gate works.

## On what remains

Before Golden Run 004 (needed to validate BC-039/040 fixes):
1. **BC-043 (critical):** Restore the truncated test_author.md prompt. This is one file edit — check git history for the original content, close the code fence, add the missing closing section.
2. **BC-046 (high):** Fix resume-after-gate-fail — the `_has_prior_gate_fail` guard exists but doesn't prevent resubmission of the specific artifact that was just rejected.
3. **BC-050 (medium):** Fix interface_architect.md worked example to use `X | Y` instead of `Union`.

After 004 passes with reasonable implementation rates:
4. **BC-054 (high):** Introduce PipelineRuntime namespace before parameter lists grow further.
5. **BC-055 (high):** Make missing required references (interface_ref, test_suite_ref) produce gate_fail instead of silent degradation.
6. **BC-056 (high):** Establish a default-value convention — start by moving channel family into config and actor_id generation into a config-derived function.

Then Phase 2 exit criteria can be evaluated: can the implementation stage lock ≥90% of items with auto-format + modern typing prompt? Golden Run 004 will answer this.

Before Phase 3 (fleet integration):
7. Review RFC-001 through RFC-005 and decide which to promote to active BCs. RFC-003 (auth-mode detection) is the most important — it prevents the exact v1 BC-376 bug where env var injection silently kills native providers.

## Gaps to flag

- **src/factory/prompts/test_author.md:75:** Truncated mid-code-block. Missing closing backtick fence and any concluding instructions. Every test_author invocation since creation has received a broken prompt. High pass rates mask the gap.
- **src/factory/opencode_channel.py:71:** `self._family` mutation during invoke creates a per-instance race. Only matters under concurrency (Phase 3+), but the fix (derive family per-invocation) should be done now.
- **AGENTS.md:** The orientation order says "read .factory/worklog.md" then "read reflections" — but the worklog is 347 lines of 13 sessions. New agents need a "current state" section at the top summarizing what Phase, branch, and test commands are active. Added `make` commands to address this.
- **Gate silent degradation:** gate_process.py:100-108, 114-130 silently skip interface-dependent checks when interface_ref is missing. A test_suite without interface_ref passes the gate with no mypy/import validation. This is the v1 "warn-and-continue" pattern.
- **report.py:18:** hardcoded workflow_version=1 means Phase 2 telemetry is invisible to the reporting tool. BC-033 (telemetry reporter skeleton) should incorporate this fix.
