from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from pathlib import Path

from factory.constants import GATE_NAME_ARTIFACT_OVERSIZED, MAX_ARTIFACT_SIZE_BYTES


@dataclass(frozen=True)
class GateResult:
    passed: bool
    gate_name: str
    diagnostics: list[str] = field(default_factory=list)
    artifact_valid: bool = True
    diagnostic_kind: str = ""
    skipped: bool = False
    transition_fields: dict = field(default_factory=dict)
    """Custom fields to merge into the current work item's transition payload."""
    routing_fields: dict = field(default_factory=dict)
    """Custom fields to propagate to an upstream revision created by the router."""
    routing_hint: dict | None = None
    # Deprecated: use transition_fields or routing_fields instead.
    # Kept for one migration cycle. Maps to transition_fields.
    custom_fields: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.custom_fields:
            warnings.warn(
                "GateResult.custom_fields is deprecated; use transition_fields or routing_fields",
                DeprecationWarning,
                stacklevel=2,
            )
            # Merge into transition_fields for backwards compatibility
            merged = {**self.custom_fields, **self.transition_fields}
            object.__setattr__(self, "transition_fields", merged)
            object.__setattr__(self, "custom_fields", {})


# tier: enforce
# precondition: artifact size gates must block oversized artifacts
# before they reach subprocess gates
# audit trigger: re-evaluate if MAX_ARTIFACT_SIZE_BYTES changes
# or if streaming artifact parsing is introduced
def _guard_artifact_size(artifact_path: Path) -> GateResult | None:
    try:
        size = artifact_path.stat().st_size
    except OSError:
        return None
    if size > MAX_ARTIFACT_SIZE_BYTES:
        return GateResult(
            passed=False,
            gate_name=GATE_NAME_ARTIFACT_OVERSIZED,
            diagnostics=[
                f"Artifact size {size} bytes exceeds gate limit {MAX_ARTIFACT_SIZE_BYTES} bytes"
            ],
            artifact_valid=False,
            diagnostic_kind="artifact_oversized",
        )
    return None
