from __future__ import annotations

from substrate._types import Event

from factory.workspace import ArtifactManifest


def make_manifest(
    attempt_number: int = 1,
    work_item_id: str = "wi-test",
    artifact_name: str = "artifact.pyi",
    **overrides,
) -> ArtifactManifest:
    defaults = {
        "attempt_number": attempt_number,
        "work_item_id": work_item_id,
        "artifact_name": artifact_name,
        "artifact_sha256": "sha256placeholder",
        "artifact_size": 0,
    }
    defaults.update(overrides)
    return ArtifactManifest(**defaults)


def events_by_transition(events: list[Event], transition: str) -> list[Event]:
    return [e for e in events if e.transition == transition]
