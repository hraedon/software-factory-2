from __future__ import annotations

import logging
from dataclasses import dataclass, field

log = logging.getLogger(__name__)


class EventSchemaError(Exception):
    """Raised when an event payload dict does not match the expected schema."""


def _warn_unknown_fields(cls_name: str, d: dict, known: set[str]) -> None:
    unknown = set(d.keys()) - known
    if unknown:
        log.warning("event_schema_unknown_fields: class=%s fields=%s", cls_name, sorted(unknown))


@dataclass(frozen=True)
class SubmitPayload:
    """Payload for submit transitions.

    Carries timing metadata for the worker invocation.
    Artifact references remain in custom_fields.
    """

    duration_seconds: float | None = None
    inner_gate_attempts: list[dict] | None = None

    def to_dict(self) -> dict:
        d: dict = {}
        if self.duration_seconds is not None:
            d["duration_seconds"] = self.duration_seconds
        if self.inner_gate_attempts:
            d["inner_gate_attempts"] = self.inner_gate_attempts
        return d

    @classmethod
    def from_dict(cls, d: dict) -> SubmitPayload:
        if not isinstance(d, dict):
            raise EventSchemaError("SubmitPayload must be a dict")
        _warn_unknown_fields("SubmitPayload", d, {"duration_seconds", "inner_gate_attempts"})
        duration = d.get("duration_seconds")
        if duration is not None and not isinstance(duration, (int, float)):
            raise EventSchemaError("SubmitPayload 'duration_seconds' must be a number")
        attempts = d.get("inner_gate_attempts")
        if attempts is not None and not isinstance(attempts, list):
            raise EventSchemaError("SubmitPayload 'inner_gate_attempts' must be a list")
        return cls(duration_seconds=duration, inner_gate_attempts=attempts)


@dataclass(frozen=True)
class GatePassPayload:
    """Payload for gate_pass transitions."""

    def to_dict(self) -> dict:
        return {}

    @classmethod
    def from_dict(cls, d: dict) -> GatePassPayload:
        if not isinstance(d, dict):
            raise EventSchemaError("GatePassPayload must be a dict")
        _warn_unknown_fields("GatePassPayload", d, set())
        return cls()


@dataclass(frozen=True)
class GateFailPayload:
    """Payload for gate_fail and gate_escalation transitions."""

    diagnostics: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"diagnostics": self.diagnostics}

    @classmethod
    def from_dict(cls, d: dict) -> GateFailPayload:
        if not isinstance(d, dict):
            raise EventSchemaError("GateFailPayload must be a dict")
        diagnostics = d.get("diagnostics")
        if diagnostics is None:
            raise EventSchemaError("GateFailPayload missing required field 'diagnostics'")
        if not isinstance(diagnostics, dict):
            raise EventSchemaError("GateFailPayload 'diagnostics' must be a dict")
        _warn_unknown_fields("GateFailPayload", d, {"diagnostics"})
        return cls(diagnostics=diagnostics)


@dataclass(frozen=True)
class ChannelFailPayload:
    """Payload for channel_fail transitions."""

    diagnostics: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"diagnostics": self.diagnostics}

    @classmethod
    def from_dict(cls, d: dict) -> ChannelFailPayload:
        if not isinstance(d, dict):
            raise EventSchemaError("ChannelFailPayload must be a dict")
        diagnostics = d.get("diagnostics")
        if diagnostics is None:
            raise EventSchemaError("ChannelFailPayload missing required field 'diagnostics'")
        if not isinstance(diagnostics, dict):
            raise EventSchemaError("ChannelFailPayload 'diagnostics' must be a dict")
        _warn_unknown_fields("ChannelFailPayload", d, {"diagnostics"})
        return cls(diagnostics=diagnostics)


@dataclass(frozen=True)
class CannotProceedPayload:
    """Payload for cannot_proceed transitions.

    Note: runner.py currently stores cannot_proceed diagnostics in custom_fields,
    not payload. This dataclass is provided for forward-compatible consumption and
    for any future producer that moves diagnostics into payload.
    """

    diagnostics: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"diagnostics": self.diagnostics}

    @classmethod
    def from_dict(cls, d: dict) -> CannotProceedPayload:
        if not isinstance(d, dict):
            raise EventSchemaError("CannotProceedPayload must be a dict")
        diagnostics = d.get("diagnostics")
        if diagnostics is None:
            raise EventSchemaError("CannotProceedPayload missing required field 'diagnostics'")
        if not isinstance(diagnostics, dict):
            raise EventSchemaError("CannotProceedPayload 'diagnostics' must be a dict")
        _warn_unknown_fields("CannotProceedPayload", d, {"diagnostics"})
        return cls(diagnostics=diagnostics)
