from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from factory.constants import (
    ACTOR_ID_GATE,
    ACTOR_ID_SCHEDULER,
    ACTOR_ID_WORKER_PREFIX,
    CHANNEL_CLAUDE_CODE,
    CHANNEL_CODE,
    CHANNEL_TO_FAMILY,
    CUSTOM_FIELD_INTERFACE_REF,
    CUSTOM_FIELD_TEST_SUITE_REF,
    FAMILY_ANTHROPIC,
    LINK_TYPE_DERIVED_FROM,
    LINK_TYPE_IMPLEMENTS,
    LINK_TYPE_TESTED_BY,
    ROLE_FRONTIER_JUDGE,
    ROLE_INTERFACE_ARCHITECT,
    ROLE_MECHANICAL_GATE,
    STATE_LOCKED,
    WORK_ITEM_TYPE_IMPLEMENTATION,
    WORK_ITEM_TYPE_INTERFACE_SPEC,
    WORK_ITEM_TYPE_TEST_SUITE,
)
from factory.workspace import WORK_DIR_NAME, WORK_SUBDIR


@dataclass(frozen=True)
class StageHandoff:
    source_type: str
    source_state: str
    target_type: str
    link_type: str
    additional_links: tuple[str, ...] = ()
    ref_field: str | None = None
    propagate_fields: tuple[str, ...] = ()


@dataclass(frozen=True)
class RoleConfig:
    role: str
    channel: str
    timeout_seconds: int = 600
    model: str | None = None
    provider: str | None = None
    fallback_channel: str | None = None
    fallback_model: str | None = None

    @property
    def family(self) -> str:
        return CHANNEL_TO_FAMILY.get(self.channel, FAMILY_ANTHROPIC)


_DEFAULT_WORKSPACE = Path(WORK_DIR_NAME) / WORK_SUBDIR


@dataclass(frozen=True)
class GateTimeouts:
    import_timeout: int = 60
    collect_timeout: int = 120
    ruff_timeout: int = 60
    mypy_timeout: int = 120
    pytest_timeout: int = 300


@dataclass(frozen=True)
class OpsConfig:
    workspace_max_age_hours: int = 168
    archive_before_delete: bool = True
    preserve_failed_hours: int = 24
    log_max_size_bytes: int = 10_000_000
    log_backup_count: int = 5
    log_max_age_hours: int = 168
    disk_alert_warning_percent: float = 80.0
    disk_alert_error_percent: float = 90.0
    max_memory_rss_mb: int = 2048
    gate_subprocess_timeout_multiplier: float = 1.5


@dataclass(frozen=True)
class FactoryConfig:
    workflow_name: str = "software_factory"
    workflow_version: int = 1
    dsn: str = "postgresql://substrate_test:substrate_test@localhost:5432/substrate_test"
    hmac_key_path: str = "test_keys.json"
    project_name: str = "sf2"
    workspace_root: Path = _DEFAULT_WORKSPACE
    spec_file: Path | None = None
    poll_interval_seconds: int = 5
    claim_ttl_seconds: int = 300
    attempt_threshold: int = 3
    worker_roles: tuple[str, ...] = (ROLE_INTERFACE_ARCHITECT,)
    gate_roles: tuple[str, ...] = (ROLE_MECHANICAL_GATE,)
    type_to_role: tuple[tuple[str, str], ...] = (
        (WORK_ITEM_TYPE_INTERFACE_SPEC, ROLE_INTERFACE_ARCHITECT),
    )
    roles: tuple[RoleConfig, ...] = (
        RoleConfig(role=ROLE_INTERFACE_ARCHITECT, channel=CHANNEL_CLAUDE_CODE),
        RoleConfig(role=ROLE_MECHANICAL_GATE, channel=CHANNEL_CODE),
    )
    query_page_size: int = 50
    telemetry_event_limit: int = 500
    per_channel_timeout: dict[str, int] | None = None
    use_project_venv: bool | None = None
    inner_gate_retries: int = 3
    inner_gate_max_feedback_chars: int = 2000
    jury_quorum: int = 2
    channel_backoff_base_seconds: int = 30
    channel_backoff_max_attempts: int = 3
    empty_output_retries: int = 1
    empty_output_retry_delay_seconds: int = 3
    credentials_path: Path | None = None
    invocation_cwd: Path | None = None
    gate_crash_threshold: int = 3
    gate_timeouts: GateTimeouts = field(default_factory=GateTimeouts)
    ops: OpsConfig = field(default_factory=OpsConfig)
    stage_topology: tuple[StageHandoff, ...] = (
        StageHandoff(
            source_type=WORK_ITEM_TYPE_INTERFACE_SPEC,
            source_state=STATE_LOCKED,
            target_type=WORK_ITEM_TYPE_TEST_SUITE,
            link_type=LINK_TYPE_DERIVED_FROM,
            ref_field=CUSTOM_FIELD_INTERFACE_REF,
        ),
        StageHandoff(
            source_type=WORK_ITEM_TYPE_TEST_SUITE,
            source_state=STATE_LOCKED,
            target_type=WORK_ITEM_TYPE_IMPLEMENTATION,
            link_type=LINK_TYPE_TESTED_BY,
            additional_links=(LINK_TYPE_IMPLEMENTS,),
            ref_field=CUSTOM_FIELD_TEST_SUITE_REF,
            propagate_fields=(CUSTOM_FIELD_INTERFACE_REF,),
        ),
    )

    @classmethod
    def phase2(cls, **overrides) -> FactoryConfig:
        from factory.phase_defaults import (
            PHASE2_ROLES,
            PHASE2_TYPE_TO_ROLE,
            PHASE2_WORKER_ROLES,
        )

        return cls(
            workflow_version=2,
            worker_roles=PHASE2_WORKER_ROLES,
            type_to_role=PHASE2_TYPE_TO_ROLE,
            roles=PHASE2_ROLES,
            **overrides,
        )

    @classmethod
    def phase3(cls, **overrides) -> FactoryConfig:
        from factory.phase_defaults import (
            PHASE3_ROLES,
            PHASE3_TYPE_TO_ROLE,
            PHASE3_WORKER_ROLES,
        )

        return cls(
            workflow_version=3,
            worker_roles=PHASE3_WORKER_ROLES,
            type_to_role=PHASE3_TYPE_TO_ROLE,
            roles=PHASE3_ROLES,
            **overrides,
        )

    @classmethod
    def phase4(cls, **overrides) -> FactoryConfig:
        from factory.phase_defaults import (
            PHASE4_ROLES,
            PHASE4_STAGE_TOPOLOGY,
            PHASE4_TYPE_TO_ROLE,
            PHASE4_WORKER_ROLES,
        )

        return cls(
            workflow_version=4,
            worker_roles=PHASE4_WORKER_ROLES,
            type_to_role=PHASE4_TYPE_TO_ROLE,
            roles=PHASE4_ROLES,
            stage_topology=PHASE4_STAGE_TOPOLOGY,
            **overrides,
        )

    @classmethod
    def phase5(cls, **overrides) -> FactoryConfig:
        from factory.phase_defaults import (
            PHASE5_ROLES,
            PHASE5_STAGE_TOPOLOGY,
            PHASE5_TYPE_TO_ROLE,
            PHASE5_WORKER_ROLES,
        )

        return cls(
            workflow_version=5,
            worker_roles=PHASE5_WORKER_ROLES,
            type_to_role=PHASE5_TYPE_TO_ROLE,
            roles=PHASE5_ROLES,
            stage_topology=PHASE5_STAGE_TOPOLOGY,
            **overrides,
        )

    def worker_actor_id(self, channel_name: str) -> str:
        return f"{ACTOR_ID_WORKER_PREFIX}-{channel_name}"

    @property
    def gate_actor_id(self) -> str:
        return ACTOR_ID_GATE

    def validate_jury_config(self) -> list[str]:
        warnings: list[str] = []
        judge_roles = [r for r in self.roles if r.role == ROLE_FRONTIER_JUDGE]
        if judge_roles and self.jury_quorum > 1:
            distinct_models = len({(r.channel, r.model) for r in judge_roles})
            if distinct_models < self.jury_quorum:
                warnings.append(
                    f"jury_quorum={self.jury_quorum} but only {distinct_models} distinct "
                    f"model(s) for frontier_judge — same-model jurors will systematically "
                    f"disagree. Set jury_quorum=1 for single-family configs."
                )
        return warnings

    @property
    def scheduler_actor_id(self) -> str:
        return ACTOR_ID_SCHEDULER

    def get_role_config(self, role: str) -> RoleConfig | None:
        for rc in self.roles:
            if rc.role == role:
                return rc
        return None

    def role_for_type(self, work_item_type: str) -> str | None:
        for type_name, role_name in self.type_to_role:
            if type_name == work_item_type:
                return role_name
        return None

    def stage_handoff_for(self, source_type: str, source_state: str) -> StageHandoff | None:
        for handoff in self.stage_topology:
            if handoff.source_type == source_type and handoff.source_state == source_state:
                return handoff
        return None

    def should_use_project_venv(self) -> bool:
        if self.use_project_venv is None:
            return (self.workspace_root / "requirements.txt").exists()
        return self.use_project_venv

    @classmethod
    def from_yaml(cls, path: str | Path) -> FactoryConfig:
        raw = yaml.safe_load(Path(path).read_text())
        kwargs: dict = dict(raw)
        if "workspace_root" in kwargs and isinstance(kwargs["workspace_root"], str):
            kwargs["workspace_root"] = Path(kwargs["workspace_root"])
        if "spec_file" in kwargs and isinstance(kwargs["spec_file"], str):
            kwargs["spec_file"] = Path(kwargs["spec_file"])
        if "credentials_path" in kwargs and isinstance(kwargs["credentials_path"], str):
            kwargs["credentials_path"] = Path(kwargs["credentials_path"])
        if "invocation_cwd" in kwargs and isinstance(kwargs["invocation_cwd"], str):
            kwargs["invocation_cwd"] = Path(kwargs["invocation_cwd"])
        if "roles" in kwargs:
            if isinstance(kwargs["roles"], dict):
                raise TypeError("'roles' must be a list, got dict")
            kwargs["roles"] = tuple(RoleConfig(**r) for r in kwargs["roles"])
        if "worker_roles" in kwargs:
            if isinstance(kwargs["worker_roles"], str):
                kwargs["worker_roles"] = (kwargs["worker_roles"],)
            else:
                kwargs["worker_roles"] = tuple(kwargs["worker_roles"])
        if "gate_roles" in kwargs:
            if isinstance(kwargs["gate_roles"], str):
                kwargs["gate_roles"] = (kwargs["gate_roles"],)
            else:
                kwargs["gate_roles"] = tuple(kwargs["gate_roles"])
        if "type_to_role" in kwargs:
            kwargs["type_to_role"] = tuple(tuple(pair) for pair in kwargs["type_to_role"])
        if "gate_timeouts" in kwargs and isinstance(kwargs["gate_timeouts"], dict):
            kwargs["gate_timeouts"] = GateTimeouts(**kwargs["gate_timeouts"])
        if "stage_topology" in kwargs:
            topo = kwargs["stage_topology"]
            if isinstance(topo, list):
                handoffs: list[StageHandoff] = []
                for item in topo:
                    if isinstance(item, dict):
                        for list_field in ("additional_links", "propagate_fields"):
                            if list_field in item and isinstance(item[list_field], list):
                                item[list_field] = tuple(item[list_field])
                        handoffs.append(StageHandoff(**item))
                    elif isinstance(item, StageHandoff):
                        handoffs.append(item)
                kwargs["stage_topology"] = tuple(handoffs)
        if "ops" in kwargs and isinstance(kwargs["ops"], dict):
            kwargs["ops"] = OpsConfig(**kwargs["ops"])
        cfg = cls(**kwargs)
        jury_warnings = cfg.validate_jury_config()
        for w in jury_warnings:
            import logging

            logging.getLogger(__name__).warning(w)
        return cfg

    @classmethod
    def from_yaml_or_default(cls, path: str | Path | None) -> FactoryConfig:
        if path is not None:
            p = Path(path)
            if p.exists():
                return cls.from_yaml(p)
        return cls()


def load_config(config_path: str | None) -> FactoryConfig:
    return FactoryConfig.from_yaml_or_default(config_path)
