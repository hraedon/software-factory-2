---
model: fireworks-ai/accounts/fireworks/routers/kimi-k2p6-turbo
datetime: 2026-05-11T06:45 UTC
project: software-factory-2
---

# Session Reflection — 2026-05-11

**Work summary:** Adversarial review of the entire v2 codebase, resolving 8 defects
(flagged as high/critical/medium) in code and opening 16 new breadcrumbs for
remaining issues. All changes pass `make check` (424 tests, 0 lint, 0 audit).

---

## On the project

The codebase is in better shape than most agent-pipeline projects I've seen.
The constants-centralization discipline is real and working — there is no "string
constant gravity" drifting across files. The gate layer is well-factored enough
that fixing 5 separate bugs in it took <30 minutes total. That said, the
adversarial lens surfaced a pattern: the project is *slightly* too comfortable
with `except SyntaxError: pass`. Three instances survived to Phase 3, and one
would have let invalid code through to model channels silently. The test suite
(424 tests) is broad but shallow on adversarial cases — no fuzzing of channel
output extraction, no path-traversal injection tests, no size-limit DoS tests.

The spec's Phase 3 telemetry-driven model placement is a genuinely good idea,
but GR-015 is about to run with adapters the team itself says are unvalidated.
If those runs fail, the telemetry will be adapter-shaped, not model-shaped,
undermining the whole point of Phase 3.

## On the work done

I'm confident in the 8 resolved items:
- Inner-gate retry subdirectory (BC-088) is structurally correct and preserves
  the original artifact.
- Stub gate (BC-089), kwonlyargs (BC-090), relative imports (BC-091), and
  SyntaxError swallowing (BC-092) are all well-scoped single-file changes with
  clear test coverage.
- `MAX_ARTIFACT_SIZE_BYTES` (BC-095) is a 1 MB cap enforced at two layers
  (runner before `read_bytes()`, channel before writing `raw_stdout.txt`).

The one fix I'd want a second pair of eyes on: the `_check_pyi_stub` rewrite
(BC-089). I changed the logic from "accept any Constant" to "only accept
Ellipsis or Pass". This is correct per spec §4 Stage 2, but it might reject
stubs that include type-variable docstrings the team intended to allow. If the
next golden run sees stub-gate failures spike, that's the first place to look.

## On what remains

**Before GR-015 (immediate):**
1. Isolate smoke-test each unvalidated adapter (DeepSeek via opencode, GLM via
   opencode, Gemini CLI) on a single work-item. Only mix into GR-015 after
   passing. (BC-107, BC-108)
2. Size-limit the gate layer itself (BC-104) — runner is guarded but gate/pre_gate
   still call `read_bytes()` unbounded.

**Before Phase 4 (next phase):**
3. Fix scheduler pagination-unsafe idempotency (BC-102). At non-trivial scale
   this will duplicate downstream work items.
4. Add adversarial tests for output extraction (BC-110) — the regex-based
   parsing is the most fragile surface in the whole pipeline.

**Nice to have:**
5. Circuit breaker for failing channels (BC-109).
6. `make golden-run` process supervision (BC-106).

## Gaps to flag

- **`src/factory/output_extraction.py:7-18`** — `extract_artifact_from_output` uses
  a greedy regex on triple-backticks. If a model emits multiple fenced blocks,
  it may capture prose instead of code. No adversarial tests exist (BC-110).
- **`src/factory/output_extraction.py:28-32`** — JSON extraction uses a naive
  `\{[\s\S]*?\}` regex that is not JSON-aware. Can match truncated objects
  and silently fall through (BC-101).
- **`src/factory/scheduler.py:86-95`** — `_ensure_downstream_item` queries all
  work items of a type and iterates O(N). Pagination unsafe; duplicate items
  possible at scale (BC-102).
- **`src/factory/credentials.py:55-62`** — `redact_value` has a math bug for short
  keys (`visible = min(4, len(value) - 4)` yields negative for len < 4).
  Security-UX issue (BC-097).
- **`populate_work_items.py:112-116`** — `--reset` calls `shutil.rmtree` on an
  arbitrary path from config YAML. No path guard (BC-096).
- **`src/factory/pre_gate.py:356-396`** — `_run_ruff_fast` mutates the artifact
  file in-place with `ruff check --fix`. Side effect on retry prompt context
  (BC-114).
- **No DeepSeek standalone adapter** — `_create_channels` only knows Claude,
  OpenCode, Gemini. `FAMILY_OLLAMA` in constants is orphaned (BC-112).
