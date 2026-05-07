---
model: deepseek-v4-pro
datetime: 2026-05-07T01:57 UTC
project: software-factory-2
---

# Session Reflection — 2026-05-06/07

**Work summary:** Executed Opus's 4-phase golden-run test plan end-to-end. Fixed 6 bugs (3 critical — missing claim transition, context override, adversarial check), added raw_stdout capture and structural-equivalence testing, ran the full 11-item measurement twice (10/10 both times), performed semantic spot-checks on three shapes, and filed 6 breadcrumbs. Phase 1 exit criteria met at 100% first-attempt pass rate. All forensic artifacts committed under `phase1-exit` tag.

---

## On the project

The factory's Phase 1 is genuinely ready. Not "ready if you squint" — the pipeline processes 11 .pyi-producing specs through Claude and a mechanical gate cleanly in ~3.5 minutes, with zero extraction failures and zero false negatives. The architecture (substrate spine, separate runner/gate processes, channel adapter pattern) is clean enough that adding roles in Phase 2 will be additive rather than remedial.

The test suite is the weak link. 67 tests passed before this session despite two high-severity bugs (missing claim transition, context content override). The tests are thorough within their boundaries — gate evaluation, workspace integrity, mock pipeline paths — but the boundaries leave gaps at the integration seams (worker_loop hot path, spec_file configuration). Each new role in Phase 2 will create the same pattern of untested seams unless the testing approach scales up alongside the role count.

The `interface_architect.md` prompt is the strongest artifact in the project. Claude produced exactly what was asked every time: single-fenced blocks, no chat, no hedging. The structured-failure path (`cannot_proceed.json` via fenced JSON block) worked on first contact with the adversarial item. This is unusually good prompt compliance and means the factory doesn't need to get clever about extraction heuristics.

## On the work done

Confidence is high on everything committed. The claim transition fix (runner.py:91-101) is architecturally correct — `acquire_claim` is a DB-level lease, `transition("claim")` is the state-level event, and both are necessary. The context fix (context.py:46-47) now correctly prefers work-item content with factory spec as fallback only when the work-item has no content. The structural equivalence function in gate.py actually catches real differences (different class names between two acquire_claim .pyi files from the same spec) while ignoring formatting — it's doing useful work already.

The only thing that felt fragile was the substrate import situation. `uv run` keeps reinstalling PyPI `substrate` over the local editable due to `uv.lock`. Every command that touches substrate (populate, run, gate, report) must either use `.venv/bin/python3` directly or be preceded by `uv pip install -e /projects/substrate --reinstall`. This is a harness issue, not a factory issue, but it makes the runbook harder to reproduce than it should be. If someone clones this repo fresh, they'll hit this.

The re-run (having to re-populate and re-measure after the BC-010 workspace cleanup test nuked the forensics) was annoying but proved an important point: the pipeline is reproducible. 10/10 both times.

## On what remains

**Before Phase 2 starts:**
- BC-011 and BC-012 should be implemented (test gaps for claim transition + spec_file path). These are genuinely important — each new role will create new untested seams, and fixing the known ones first sets a standard.
- BC-013 should be read before any Phase 2 design work. The semantic gating question is the central architectural decision of Phase 2, and the approach chosen (inline with roles, separate sub-phase, or hybrid) changes the implementation order.

**Phase 2 roll-out:**
- Add roles in pipeline order: test_author → implementer → cross_family_reviewer → frontier_judge. Each role needs its own prompt, its own gate, and integration tests that exercise the full role chain up to that point, not just the new role in isolation.
- The `structural_signature()` function should be adapted for each role's artifact format. Tests have different structural elements (test function names, assert patterns) than .pyi stubs, and implementations have different elements still.

**Nice to have:**
- Fix the substrate import situation. Options: stop using `uv run` entirely (use venv python directly), pin local substrate path in pyproject.toml instead of `>=0.1.0`, or add a wrapper script that does the install-and-run dance.

## Gaps to flag

- **`tests/test_runner_smoke.py` uses MockSubstrate, never exercises the claim transition path.** The smoke tests pass but don't assert the worker_loop writes a `claim` event. BC-011 captures this. Location: `tests/test_runner_smoke.py:59` and surrounding.

- **`tests/test_context.py` never passes `spec_content` to `derive_context`.** All tests construct `PromptContext` directly or use `_serialize_bundle`. BC-012 captures this. Location: `tests/test_context.py` — entire module.

- **`uv.lock` pins PyPI substrate 220240617.1.8 which shadows the local `/projects/substrate`.** Every `uv run` invocation re-installs the wrong package. This is a harness-level irritant but it will bite anyone trying to reproduce the golden run from a fresh clone. Location: `uv.lock:substrate` entry.

- **The populate script's `_open_or_create_project` imports `substrate._testing.drop_project_schema` inline on every reset.** This is a private API dependency that would break if substrate renames `_testing`. It's used in tests too (conftest.py), so the blast radius is contained, but it's fragile. Location: `populate_work_items.py:32`.

- **`evaluate_interface_spec` does not check return types, parameter names, or function count.** A stub that defines `acquire_claim(x: float) -> None` with `"""Satisfies AC-06."""` passes all gates. Semantic spot-checks on 01/04/07 confirmed Claude didn't do this, but nothing prevents it. BC-013 captures this as a design question. Location: `src/factory/gate.py:16-47`.
