---
number: "056"
title: "No single-source-of-truth rule for default values — v1 'string constant gravity' pattern risk"
severity: high
status: resolved
kind: design
author: adversarial-review
date: "2026-05-08"
tags: [config, runner, dep-v1-defaults]
related: ["041"]
---

## Problem

v1 suffered from "string constant gravity": the default provider `"claude"` accreted into 7 independent copies of `os.environ.get("FACTORY_AGENT_PROVIDER", "claude")` across 5 files. Each copy was a reasonable local decision but collectively created a shadow configuration layer that bypassed the role system.

v2 currently has a clean `FactoryConfig` dataclass — all defaults are centralized in one file. This is correct design. But there is no codified rule preventing the pattern from recurring, and early signs of drift exist:

- `runner.py:71`: `actor_id = f"factory-worker-{channel.name}"` — a runtime-concatenated identifier not derived from config.
- `gate_process.py:33`: `actor_id = "factory-gate-code"` — hardcoded.
- `scheduler.py:105`: `actor_id="factory-scheduler"` — hardcoded in `create_work_item` calls.
- `report.py:9-10`: DSN and KEY_PATH hardcoded as module-level constants.
- `claude_code_channel.py:22`: `self._family = "anthropic"` — hardcoded. `opencode_channel.py:34`: `self._family = "opencode"` — hardcoded.

None of these are yet a problem (single-channel, single-worker mode), but each is a new accretion point. When Phase 3 adds multi-channel and Phase 4 adds concurrent workers, these scattered defaults will silently diverge.

## Fix

1. Add a convention to `AGENTS.md`: "Default values live in `FactoryConfig` or are derived from it. No inline defaults, no hardcoded identifiers, no bare strings in function bodies that could appear in another file."
2. Move `actor_id` generation into config (or a `PipelineRuntime` namespace per BC-054).
3. Move channel `family` into `FactoryConfig` (or `RoleConfig`) rather than hardcoding in each adapter.
4. Wire `report.py` to read config rather than hardcoding connection params.

## Resolution

Created `factory/constants.py` as the single source of truth for all identifier strings used across the codebase. Every string that appeared in more than one file — work item types, role names, state names, transition names, custom field keys, link types, channel names, actor IDs, artifact filenames, tempfile prefixes, and provider-family mappings — now lives in one module and is imported everywhere else.

Specific changes:

1. `AGENTS.md` already had the convention (added during BC-056 proposal). Verified it is present.
2. `factory/constants.py` — new module with 40+ named constants: `WORK_ITEM_TYPE_*`, `ROLE_*`, `CHANNEL_*`, `FAMILY_*`, `STATE_*`, `TRANSITION_*`, `LINK_TYPE_*`, `CUSTOM_FIELD_*`, `ACTOR_ID_*`, `ACTOR_KIND_*`, `ARTIFACT_FILENAME_*`, `TEMPFILE_PREFIX_*`, `FAMILY_BY_PROVIDER`.
3. `FactoryConfig` now references constants for all default values; added `worker_actor_id(channel_name)`, `gate_actor_id`, and `scheduler_actor_id` properties. `RoleConfig.family` property derives family from channel name.
4. All 11 source files refactored to import from `constants.py` instead of bare strings: `runner.py`, `gate_process.py`, `scheduler.py`, `router.py`, `context.py`, `failure_summary.py`, `claude_code_channel.py`, `opencode_channel.py`, `gate.py`, `report.py`, `populate_work_items.py`.
5. 264 tests pass, 0 lint errors.
