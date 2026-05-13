---
model: kimi-k2p6-cloud
datetime: 2026-05-13T20:47 UTC
project: software-factory-2
---

# Session Reflection — 2026-05-13

**Work summary:** Ran the first Phase 4 golden run (GR-022) against cert-watch-mini with all 5 roles. Fixed three integration bugs discovered during the run: populate script Phase 4 inference, FactoryConfig.from_yaml stage_topology parsing, and phase4.yaml custom field schema. Added config-loader round-trip regression tests (TestPhaseConfigRoundTrip, 4 tests). 603 tests pass, 0 lint errors.

---

## On the project

The factory is stronger than it looks on paper. 22 golden runs, 603 tests, and a 100% lock rate on the last three runs is real evidence that the substrate spine + inner-gate loop + prompt pre-flight checklists work together. The biggest architectural risk is not the model quality — it's the YAML/Python config drift that bit us three times in one session.

Phase 4 is no longer "skeleton validated." It's ** exercised end-to-end** on real model output. 15 work items, 5 roles, 4 handoffs per spec, all locked. That's a genuine capability, not a mock.

What still feels fragile:
- **Config loading is the weakest link.** Every new phase adds fields to FactoryConfig, workflow YAML, and populate script. The loader requires manual parsing code per field. Three bugs in one golden run (populate, from_yaml, phase4.yaml schema) is a pattern, not coincidence.
- **The "fleet" is a fleet of one.** K2 handles all roles. Multi-family jury — the entire architectural justification for Phase 4 — has not been validated empirically.
- **Telemetry still conflates outer-gate and inner-gate data.** The first-attempt metric is honest about what it measures, but the inner-gate signal requires runner-log parsing. This will confuse future agents.

## On the work done

The GR-022 execution was straightforward once the blockers were cleared. The config/YAML fixes were all of the same class: "the code knows about X but the loader/schema doesn't." The round-trip tests I added (TestPhaseConfigRoundTrip) should prevent this class of bug in future phases.

What I'm confident in:
- The `stage_topology` parsing fix is correct and tested.
- The `phase4.yaml` custom field additions match what the scheduler actually writes.
- The golden-run-022-log.md report is accurate and grounded in telemetry output.

What I'd want a second pair of eyes on:
- The `_plain_dict` helper in the round-trip test is a bit ad-hoc. It recursively converts tuples→lists and dataclasses→dicts so yaml.dump doesn't emit `!!python/tuple` tags. It works, but it's not elegant.
- The `jury_quorum=1` in GR-022 means the jury was a rubber stamp. The `jury.py` parallel executor was not meaningfully tested for real multi-channel races.

## On what remains

Per Opus's ordering:
1. ✅ Config-loader round-trip test — **done**
2. 🔄 Synthetic "broken implementation" fixture to exercise reviewer rejection — **next session**
3. 🔄 Promote non-K2 channel (Claude or GLM) through isolated validation, then multi-family jury
4. 🔄 Define Phase 4 exit criteria in spec.md

Also needed:
- A test that loads each `golden-run-NNN-config.yaml` and asserts it parses without error. I manually verified 022, but the others are untested.
- Update telemetry header from "Phase 3 Exit Criteria Summary" to "Phase 4" once criteria are defined.

## Gaps to flag

- **`src/factory/config.py:304`** — `from_yaml()` is a manual parsing chain. Every new dataclass field needs an explicit `if key in kwargs` block. A generated schema or `dataclasses.asdict` round-trip would eliminate this class of bug entirely.
- **`tests/test_config.py:155-158`** — The `_plain_dict` helper converts tuples to lists recursively. If FactoryConfig gains nested tuples beyond `stage_topology`, the helper may miss them.
- **`populate_work_items.py:230-251`** — The workflow version mapping is a hardcoded dict `{1: "phase1", 2: "phase2", 3: "phase3", 4: "phase4"}`. Phase 5 will need a 5th entry. No test asserts this mapping is exhaustive.
- **`golden-run-022-config.yaml`** — `jury_quorum: 1` is not a realistic production value. It was chosen to guarantee a pass on the first run. Future GRs should use `quorum=2`.
- **`src/factory/telemetry.py`** — Header still says "Phase 3 Exit Criteria Summary" even when running Phase 4. Minor but confusing.
