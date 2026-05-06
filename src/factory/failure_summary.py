from __future__ import annotations

import json
from dataclasses import dataclass

from substrate import Substrate


@dataclass(frozen=True)
class FailureEntry:
    attempt_number: int
    role: str
    channel: str
    gate_name: str
    diagnostic: str
    actor_metadata: dict | None = None


def derive_failures(substrate: Substrate, work_item_id: str) -> list[FailureEntry]:
    events = substrate.read_events(work_item_id=work_item_id, limit=1000)
    failures: list[FailureEntry] = []
    for event in events:
        if event.transition != "gate_fail":
            continue
        meta = event.actor_metadata or {}
        diagnostics = {}
        if event.payload and "diagnostics" in event.payload:
            diagnostics = event.payload["diagnostics"]
        failures.append(
            FailureEntry(
                attempt_number=_attempt_from_meta(meta),
                role=meta.get("role", "unknown"),
                channel=meta.get("channel", "unknown"),
                gate_name=diagnostics.get("gate_name", "unknown"),
                diagnostic=diagnostics.get("message", ""),
                actor_metadata=meta,
            )
        )
    return failures


def failures_to_json(failures: list[FailureEntry]) -> str:
    entries = []
    for f in failures:
        d = {
            "attempt_number": f.attempt_number,
            "role": f.role,
            "channel": f.channel,
            "gate_name": f.gate_name,
            "diagnostic": f.diagnostic,
        }
        entries.append(d)
    return json.dumps(entries, indent=2)


def _attempt_from_meta(meta: dict) -> int:
    return meta.get("attempt_n", 0)
