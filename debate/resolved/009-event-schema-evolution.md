---
number: "009"
title: "Event schema evolution — how do regista and consumers agree on payload shape?"
author: opencode
date: "2026-05-09"
related: ["BC-068", "RFC-002", "BC-060"]
---

## Context

Regista events carry `payload: dict` and `actor_metadata: dict` as free-form JSONB. The regista library does not validate the internal shape of these fields — it stores and replays them faithfully. Consumers (v2 factory, and potentially other projects) define their own conventions for what goes inside.

v2's telemetry bug (BC-068) illustrates the failure mode: the factory started putting gate evaluation results into `payload.diagnostics` and `custom_fields.diagnostics`, but the telemetry collector expected `gate_name` in a different location. Both the producer (`gate_process.py`) and the consumer (`telemetry.py`) changed shape independently. There was no versioning, no schema check, and no failure when the shapes diverged — only silent data degradation.

## Problem

As v2 adds more phases (Phase 3 fleet, Phase 4 jury, Phase 5 real workloads), the event payload shapes will evolve:
- New `actor_metadata` fields (model version, prompt hash, cost)
- New `payload` structures (jury votes, behavioral gate screenshots, checkpoint state)
- New `custom_fields` (behavioral_spec_ref, mutation_kill_rate)

Without a schema contract, the producer and consumer will drift again. The next drift may not be as benign as `"unknown"` gate names — it could be a lost escalation, a skipped checkpoint, or a false-positive gate pass.

## Position

**Add optional, versioned payload schemas to regista that consumers can register per transition name. The schema is validated at `append_event` time (soft validation: warn, don't reject) and at replay time.**

### Proposed design

1. **Schema registry API:**
   ```python
   sub.register_payload_schema(
       transition="gate_pass",
       version=1,
       schema={
           "gate_name": str,
           "passed": bool,
           "diagnostics": list,
       }
   )
   ```

2. **Validation mode:** `warn` (log warning on mismatch) or `strict` (raise on mismatch). Default `warn` so existing consumers are not broken.

3. **Versioning:** Each schema has an integer version. Events can optionally carry `_schema_version` in payload. Consumers can query "give me all `gate_pass` events with schema version >= 2."

4. **Rejection policy:** Regista never rejects an event for payload schema violation — that would break the append-only guarantee. It logs a warning and stores a `payload_schema_warning` flag on the event.

### Why regista and not the consumer

v2 could implement this in `gate_process.py` and `telemetry.py` independently. But:
- Other consumers (future projects, audit tools, the principal's dashboard) need the same guarantee
- Regista is the shared spine; schema enforcement belongs at the spine
- If every consumer implements its own validation, they will drift from each other

### Minimal alternative

If adding schema registry to regista is too large, the immediate fix is a **consumer-level schema contract**:
- v2 defines `factory/event_schemas.py` with dataclasses for each event type it produces
- `gate_process.py` uses these dataclasses to construct payloads
- `telemetry.py` uses the same dataclasses to read payloads
- CI includes a round-trip test: construct → serialize → deserialize → assert equal

This is weaker (only helps v2, not other consumers) but can be implemented in one session.

## Risks

| Risk | Mitigation |
|---|---|
| Schema registry adds complexity to regista | Make it optional; consumers opt-in per transition |
| Schema evolution requires migration | Versioned schemas; old events keep old versions; consumers declare minimum version |
| Principal cannot review JSON schemas | Schema definitions are simple type declarations (str, bool, list), not JSON Schema drafts |

## Blocking

Phase 3 (fleet integration). Not strictly blocking, but every phase added without schema discipline makes retrofitting harder. The cost of adding schema validation after N event types exist is O(N) retroactive work.

## Next step

1. Implement consumer-level schema in v2 (`factory/event_schemas.py`) as pilot
2. Run for 2 golden runs; measure how many schema warnings are emitted
3. If the pilot works, propose regista-level registry as a regista RFC
4. Close BC-068 and RFC-002 with schema-related resolution notes
