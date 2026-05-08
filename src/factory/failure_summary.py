from __future__ import annotations

import json
from dataclasses import dataclass

from substrate import Substrate


@dataclass(frozen=True)
class FailureEntry:
    attempt_number: int
    role: str
    channel: str
    failure_type: str = "gate_fail"
    gate_name: str = ""
    diagnostic: str = ""
    error_message: str = ""
    timed_out: bool = False
    exit_code: int | None = None
    actor_metadata: dict | None = None


def derive_failures(substrate: Substrate, work_item_id: str) -> list[FailureEntry]:
    events = substrate.read_events(work_item_id=work_item_id, limit=1000)
    failures: list[FailureEntry] = []
    for event in events:
        if event.transition in ("gate_fail", "gate_escalation"):
            meta = event.actor_metadata or {}
            diagnostics = {}
            if event.payload and "diagnostics" in event.payload:
                diagnostics = event.payload["diagnostics"]
            failures.append(
                FailureEntry(
                    attempt_number=_attempt_from_meta(meta),
                    role=meta.get("role", "unknown"),
                    channel=meta.get("channel", "unknown"),
                    failure_type=event.transition,
                    gate_name=diagnostics.get("gate_name", "unknown"),
                    diagnostic=diagnostics.get("message", ""),
                    actor_metadata=meta,
                )
            )
        elif event.transition == "channel_fail":
            payload = event.payload or {}
            meta = event.actor_metadata or {}
            diagnostics = payload.get("diagnostics", {})
            failures.append(
                FailureEntry(
                    attempt_number=_attempt_from_meta(meta),
                    role=meta.get("role", "unknown"),
                    channel=meta.get("channel", "unknown"),
                    failure_type="channel_fail",
                    error_message=diagnostics.get("error_message", ""),
                    timed_out=bool(diagnostics.get("timed_out", False)),
                    exit_code=diagnostics.get("exit_code"),
                    actor_metadata=meta,
                )
            )
    return failures


def failures_to_json(failures: list[FailureEntry]) -> str:
    entries = []
    for f in failures:
        d: dict = {
            "attempt_number": f.attempt_number,
            "role": f.role,
            "channel": f.channel,
            "failure_type": f.failure_type,
        }
        if f.failure_type in ("gate_fail", "gate_escalation"):
            d.update(gate_name=f.gate_name, diagnostic=f.diagnostic)
        elif f.failure_type == "channel_fail":
            d.update(error_message=f.error_message, timed_out=f.timed_out)
            if f.exit_code is not None:
                d["exit_code"] = f.exit_code
        entries.append(d)
    return json.dumps(entries, indent=2)


def _attempt_from_meta(meta: dict) -> int:
    return meta.get("attempt_n", 0)
