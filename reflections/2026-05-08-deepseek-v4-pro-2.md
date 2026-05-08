---
model: deepseek-v4-pro
datetime: 2026-05-08T23:10 UTC
project: software-factory-2
---

# Session Reflection — 2026-05-08

**Work summary:** Adversarial review of the full codebase surfaced 10 issues (1 critical, 4 high, 3 medium, 2 low). Two were fixed in-code (gate soft-fail on missing tooling, RoleConfig.family returning wrong value for opencode). Eight were filed as breadcrumbs 060–067. BC-059 was closed after fix.

---

## On the project

The pipeline infrastructure is genuinely sound for Phase 2. The state machine is well-tested, the three golden runs show progressive improvement (001: 100% interfaces, 002: interfaces + tests but 0 impls due to module resolution, 003: 12/12 decided test_suites + 2 locked impls + correct escalation), and the spec is rigorous. The architectural decisions are well-documented and consistent.

The weakest structural property is the test pyramid: 270 unit tests on InMemorySubstrate vs ~10 integration tests on real Postgres. The history of behavioral divergence between these backends (half a dozen breadcrumbs resolved on both the substrate and factory sides) means the confidence in "tests pass ⇒ production works" is lower than the test count suggests. The golden runs themselves found bugs the unit tests missed.

The channel adapter layer has the v1 "string constant gravity" problem but with control flow — `ClaudeCodeChannel` and `OpenCodeChannel` are 95% identical. When 4 more adapters ship in Phase 3, this will be painful.

## On the work done

The adversarial review was systematic — every source file, every test file, the substrate dependency surface, and all three golden run logs were examined. The two fixes applied are both unambiguous correctness improvements:

1. **Gate soft-fail fix**: The most impactful. Returning `passed=True` when tools aren't installed violated Principle 5 and would be silently catastrophic in production. The switch from `shutil.which()` to `sys.executable -m <tool>` is the right technical choice — it solves the PATH problem for all venv-installed tools, not just the ones on the ambient PATH. This also caught a secondary issue: `_run_mypy` previously also returned `passed=True` when `interface_pyi_path` was missing, which was changed to `passed=False` with `missing_artifact`.

2. **RoleConfig.family fix**: Small but correct. The config-level view of channel family should stay consistent with per-invocation family derivation. Without this, any code reading `RoleConfig.family` for opencode channels would get `"anthropic"` instead of `"opencode"`.

The breadcrumbs are honest about severity. BC-062 (resume-on-gate-fail still wastes budget) could arguably be critical since golden run data confirms it's actively consuming Claude budget in production runs, but it's bounded (wastes exactly 1 invocation per escalated item) so high is appropriate.

## On what remains

**Before Golden Run 004** (the stated next step in AGENTS.md):
1. BC-062 (resume-on-gate-fail) — the most impactful remaining fix. One-line change in `runner.py:process_work_item` to clear resumable artifact when prior gate_fail events exist.
2. The 10 breadcrumbs now open (060-067 + 032 + 058) should be triaged for severity and phase assignment.

**Before Phase 3 (multi-channel adapters)**:
3. BC-061 (channel code duplication) — should resolve before adding 4 more adapters, not after.
4. BC-060 (inputs_dir dead parameter) — decide the protocol contract direction.
5. BC-064 (no automated channel integration tests) — should exist before multi-channel dispatch.

**Nice to have**:
6. BC-065 (configurable page_size) — medium; no production run has hit these limits yet.
7. BC-066 (cannot_proceed overload) and BC-067 (phase2 constructor) — low; cosmetic.

## Gaps to flag

- **`gate.py:373` — string matching on test output** — `"no tests collected" in result.stdout.lower()` is fragile. Pytest output phrasing changes across versions. Prefer parsing `--collect-only` exit code or result structure.
- **`gate.py:405` — missing interface_pyi_path now returns `passed=False`** — this changes semantics for a code path that was previously `passed=True`. The tests caught this (the 9 failures in the first run were all mypy-related), and the fix was installing mypy + using `sys.executable -m`, but downstream code in `gate_process_contract.py` and integration tests that route based on this result may need review.
- **`runner.py:378` — the ONLY `NotImplementedError` in the entire codebase** — "Multi-channel dispatch not yet implemented". This is the single choke point enforcing Phase 2 single-channel constraint. If anyone wants to skip ahead to Phase 3, this is where they'd start.
- **`output_extraction.py:16` — heuristic fallback** — the fallback `startswith(("from ", "import ", "class ", "def ", "@", "# "))` means a channel output that starts with a comment gets parsed as the artifact. Could result in an empty file being submitted as the implementation.
- **`config.py:112` raises `"roles must be a list, got dict"`** — if the YAML key is renamed from `roles` to e.g. `role_configs`, this error message becomes incorrect. The message string is coupled to the YAML key name but there's no constant for that key.
