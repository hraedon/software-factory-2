from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

from substrate import Substrate

from factory.config import FactoryConfig
from factory.constants import (
    STATE_CANNOT_PROCEED,
    STATE_LOCKED,
    WORK_ITEM_TYPE_IMPLEMENTATION,
    WORK_ITEM_TYPE_INTERFACE_SPEC,
    WORK_ITEM_TYPE_TEST_SUITE,
)

_checkpoint_log = logging.getLogger("factory.checkpoint")

CHECKPOINT_VERSION = 1
DEFAULT_CHECKPOINT_DIR = ".factory/checkpoints"


@dataclass(frozen=True)
class StageCheckpoint:
    stage_type: str
    total: int
    by_state: dict[str, int]
    locked_ids: list[str]
    failed_ids: list[str]
    artifact_paths: dict[str, str]
    artifact_hashes: dict[str, str]
    timestamp: str


@dataclass(frozen=True)
class PipelineCheckpoint:
    checkpoint_version: int
    project_name: str
    workflow_name: str
    workflow_version: int
    config_hash: str
    created_at: str
    stages: list[StageCheckpoint]
    summary: dict[str, int]


def _compute_config_hash(config: FactoryConfig) -> str:
    import hashlib

    parts = [
        config.project_name,
        config.workflow_name,
        str(config.workflow_version),
        str(config.attempt_threshold),
    ]
    for rc in sorted(config.roles, key=lambda r: r.role):
        parts.extend([rc.role, rc.channel, rc.model or ""])
    blob = "|".join(parts)
    return hashlib.sha256(blob.encode()).hexdigest()[:16]


def _collect_stage_data(
    sub: Substrate,
    config: FactoryConfig,
    stage_type: str,
) -> StageCheckpoint:
    page = sub.query_work_items(
        workflow_name=config.workflow_name,
        workflow_version=config.workflow_version,
        page_size=config.query_page_size,
    )
    matching = [wi for wi in page.items if wi.work_item_type == stage_type]

    by_state: dict[str, int] = {}
    locked_ids: list[str] = []
    failed_ids: list[str] = []
    artifact_paths: dict[str, str] = {}
    artifact_hashes: dict[str, str] = {}

    for wi in matching:
        state = wi.current_state
        by_state[state] = by_state.get(state, 0) + 1
        wi_id = str(wi.work_item_id)
        if state == STATE_LOCKED:
            locked_ids.append(wi_id)
        elif state == STATE_CANNOT_PROCEED:
            failed_ids.append(wi_id)
        custom = wi.custom_fields or {}
        ap = custom.get("artifact_path")
        if ap:
            artifact_paths[wi_id] = ap
        ah = custom.get("artifact_hash")
        if ah:
            artifact_hashes[wi_id] = ah

    return StageCheckpoint(
        stage_type=stage_type,
        total=len(matching),
        by_state=by_state,
        locked_ids=sorted(locked_ids),
        failed_ids=sorted(failed_ids),
        artifact_paths=artifact_paths,
        artifact_hashes=artifact_hashes,
        timestamp=datetime.now(UTC).isoformat(),
    )


def write_checkpoint(
    sub: Substrate,
    config: FactoryConfig,
    checkpoint_dir: Path | None = None,
) -> PipelineCheckpoint:
    cp_dir = checkpoint_dir or Path(DEFAULT_CHECKPOINT_DIR)
    cp_dir.mkdir(parents=True, exist_ok=True)

    stages = [
        _collect_stage_data(sub, config, WORK_ITEM_TYPE_INTERFACE_SPEC),
        _collect_stage_data(sub, config, WORK_ITEM_TYPE_TEST_SUITE),
        _collect_stage_data(sub, config, WORK_ITEM_TYPE_IMPLEMENTATION),
    ]

    summary: dict[str, int] = {}
    for stage in stages:
        for state, count in stage.by_state.items():
            summary[state] = summary.get(state, 0) + count

    checkpoint = PipelineCheckpoint(
        checkpoint_version=CHECKPOINT_VERSION,
        project_name=config.project_name,
        workflow_name=config.workflow_name,
        workflow_version=config.workflow_version,
        config_hash=_compute_config_hash(config),
        created_at=datetime.now(UTC).isoformat(),
        stages=stages,
        summary=summary,
    )

    ts = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
    filename = f"checkpoint-{config.project_name}-{ts}.json"
    cp_path = cp_dir / filename
    cp_path.write_text(json.dumps(asdict(checkpoint), indent=2, default=str))

    latest = cp_dir / "latest.json"
    try:
        latest.unlink()
    except FileNotFoundError:
        pass
    latest.write_text(json.dumps(asdict(checkpoint), indent=2, default=str))

    _checkpoint_log.info(
        "checkpoint_written path=%s stages=%d",
        cp_path,
        len(stages),
    )
    return checkpoint


def load_checkpoint(path: Path) -> PipelineCheckpoint:
    data = json.loads(path.read_text())
    stages = [StageCheckpoint(**s) for s in data.get("stages", [])]
    return PipelineCheckpoint(
        checkpoint_version=data.get("checkpoint_version", 1),
        project_name=data["project_name"],
        workflow_name=data["workflow_name"],
        workflow_version=data["workflow_version"],
        config_hash=data.get("config_hash", ""),
        created_at=data["created_at"],
        stages=stages,
        summary=data.get("summary", {}),
    )


def load_latest_checkpoint(checkpoint_dir: Path | None = None) -> PipelineCheckpoint | None:
    cp_dir = checkpoint_dir or Path(DEFAULT_CHECKPOINT_DIR)
    latest = cp_dir / "latest.json"
    if not latest.exists():
        return None
    return load_checkpoint(latest)


def compare_checkpoints(old: PipelineCheckpoint, new: PipelineCheckpoint) -> dict:
    diff: dict = {
        "config_changed": old.config_hash != new.config_hash,
        "stages": [],
    }
    for old_stage, new_stage in zip(old.stages, new.stages):
        if old_stage.stage_type != new_stage.stage_type:
            continue
        locked_delta = len(new_stage.locked_ids) - len(old_stage.locked_ids)
        failed_delta = len(new_stage.failed_ids) - len(old_stage.failed_ids)
        diff["stages"].append(
            {
                "stage_type": old_stage.stage_type,
                "locked_delta": locked_delta,
                "failed_delta": failed_delta,
                "total_delta": new_stage.total - old_stage.total,
            }
        )
    return diff


def can_resume_from_checkpoint(
    checkpoint: PipelineCheckpoint,
    config: FactoryConfig,
) -> tuple[bool, str]:
    config_hash = _compute_config_hash(config)
    if config_hash != checkpoint.config_hash:
        return False, "Config has changed since checkpoint was written"
    if checkpoint.project_name != config.project_name:
        return False, f"Project name mismatch: {checkpoint.project_name} vs {config.project_name}"
    return True, "OK"


def list_checkpoints(checkpoint_dir: Path | None = None) -> list[Path]:
    cp_dir = checkpoint_dir or Path(DEFAULT_CHECKPOINT_DIR)
    if not cp_dir.exists():
        return []
    return sorted(p for p in cp_dir.glob("checkpoint-*.json"))
