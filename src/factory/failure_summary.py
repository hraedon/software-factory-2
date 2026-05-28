from __future__ import annotations

import json
from dataclasses import dataclass

from regista import Regista

from factory.constants import (
    GATE_NAME_UNKNOWN,
    TRANSITION_CHANNEL_FAIL,
    TRANSITION_GATE_ESCALATION,
    TRANSITION_GATE_FAIL,
)
from factory.event_schemas import ChannelFailPayload, EventSchemaError, GateFailPayload


@dataclass(frozen=True)
class FailureEntry:
    attempt_number: int
    role: str
    channel: str
    failure_type: str = TRANSITION_GATE_FAIL
    gate_name: str = ""
    diagnostic: str = ""
    error_message: str = ""
    timed_out: bool = False
    exit_code: int | None = None
    actor_metadata: dict | None = None
    gate_output: str = ""


def derive_failures(regista: Regista, work_item_id: str) -> list[FailureEntry]:
    events = regista.read_events(work_item_id=work_item_id, limit=1000)
    failures: list[FailureEntry] = []
    for event in events:
        if event.transition in (TRANSITION_GATE_FAIL, TRANSITION_GATE_ESCALATION):
            meta = event.actor_metadata or {}
            gate_name = meta.get("gate_name")
            if not gate_name:
                diagnostics: dict = {}
                if event.payload:
                    try:
                        parsed = GateFailPayload.from_dict(event.payload)
                        diagnostics = parsed.diagnostics
                    except EventSchemaError:
                        diagnostics = event.payload.get("diagnostics", {})
                gate_name = diagnostics.get("gate_name", GATE_NAME_UNKNOWN)
            failures.append(
                FailureEntry(
                    attempt_number=_attempt_from_meta(meta),
                    role=meta.get("role", "unknown"),
                    channel=meta.get("channel", "unknown"),
                    failure_type=event.transition,
                    gate_name=gate_name,
                    diagnostic=_extract_diagnostic_message(event),
                    gate_output=_extract_gate_output(event),
                    actor_metadata=meta,
                )
            )
        elif event.transition == TRANSITION_CHANNEL_FAIL:
            payload = event.payload or {}
            meta = event.actor_metadata or {}
            diagnostics: dict = {}
            if payload:
                try:
                    parsed = ChannelFailPayload.from_dict(payload)
                    diagnostics = parsed.diagnostics
                except EventSchemaError:
                    diagnostics = payload.get("diagnostics", {})
            failures.append(
                FailureEntry(
                    attempt_number=_attempt_from_meta(meta),
                    role=meta.get("role", "unknown"),
                    channel=meta.get("channel", "unknown"),
                    failure_type=TRANSITION_CHANNEL_FAIL,
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
        if f.failure_type in (TRANSITION_GATE_FAIL, TRANSITION_GATE_ESCALATION):
            d.update(gate_name=f.gate_name, diagnostic=f.diagnostic)
            if f.gate_output:
                d["gate_output"] = f.gate_output
        elif f.failure_type == TRANSITION_CHANNEL_FAIL:
            d.update(error_message=f.error_message, timed_out=f.timed_out)
            if f.exit_code is not None:
                d["exit_code"] = f.exit_code
        entries.append(d)
    return json.dumps(entries, indent=2)


def _attempt_from_meta(meta: dict) -> int:
    return meta.get("attempt_n", 0)


def _extract_diagnostic_message(event) -> str:
    payload = event.payload or {}
    diagnostics = payload.get("diagnostics", {})
    return diagnostics.get("message", "")


def _extract_gate_output(event) -> str:
    payload = event.payload or {}
    diagnostics = payload.get("diagnostics", {})
    messages = diagnostics.get("messages")
    if isinstance(messages, list):
        return "\n".join(str(m) for m in messages)
    return diagnostics.get("message", "")
