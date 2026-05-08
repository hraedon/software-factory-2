from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from factory.constants import (
    ACTOR_ID_GATE,
    ACTOR_ID_SCHEDULER,
    ACTOR_ID_WORKER_PREFIX,
    CHANNEL_CLAUDE_CODE,
    CHANNEL_CODE,
    FAMILY_ANTHROPIC,
    FAMILY_CODE,
    ROLE_IMPLEMENTER,
    ROLE_INTERFACE_ARCHITECT,
    ROLE_MECHANICAL_GATE,
    ROLE_TEST_AUTHOR,
    WORK_ITEM_TYPE_IMPLEMENTATION,
    WORK_ITEM_TYPE_INTERFACE_SPEC,
    WORK_ITEM_TYPE_TEST_SUITE,
)
from factory.workspace import WORK_DIR_NAME, WORK_SUBDIR


@dataclass(frozen=True)
class RoleConfig:
    role: str
    channel: str
    timeout_seconds: int = 600
    model: str | None = None

    @property
    def family(self) -> str:
        if self.channel == CHANNEL_CLAUDE_CODE:
            return FAMILY_ANTHROPIC
        if self.channel == CHANNEL_CODE:
            return FAMILY_CODE
        return FAMILY_ANTHROPIC


_DEFAULT_WORKSPACE = Path(WORK_DIR_NAME) / WORK_SUBDIR


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

    PHASE2_WORKER_ROLES: tuple[str, ...] = (
        ROLE_INTERFACE_ARCHITECT,
        ROLE_TEST_AUTHOR,
        ROLE_IMPLEMENTER,
    )
    PHASE2_TYPE_TO_ROLE: tuple[tuple[str, str], ...] = (
        (WORK_ITEM_TYPE_INTERFACE_SPEC, ROLE_INTERFACE_ARCHITECT),
        (WORK_ITEM_TYPE_TEST_SUITE, ROLE_TEST_AUTHOR),
        (WORK_ITEM_TYPE_IMPLEMENTATION, ROLE_IMPLEMENTER),
    )
    PHASE2_ROLES: tuple[RoleConfig, ...] = (
        RoleConfig(role=ROLE_INTERFACE_ARCHITECT, channel=CHANNEL_CLAUDE_CODE),
        RoleConfig(role=ROLE_TEST_AUTHOR, channel=CHANNEL_CLAUDE_CODE),
        RoleConfig(role=ROLE_IMPLEMENTER, channel=CHANNEL_CLAUDE_CODE),
        RoleConfig(role=ROLE_MECHANICAL_GATE, channel=CHANNEL_CODE),
    )

    def worker_actor_id(self, channel_name: str) -> str:
        return f"{ACTOR_ID_WORKER_PREFIX}-{channel_name}"

    @property
    def gate_actor_id(self) -> str:
        return ACTOR_ID_GATE

    @property
    def scheduler_actor_id(self) -> str:
        return ACTOR_ID_SCHEDULER

    def get_role_config(self, role: str) -> RoleConfig | None:
        for rc in self.roles:
            if rc.role == role:
                return rc
        return None

    @classmethod
    def from_yaml(cls, path: str | Path) -> FactoryConfig:
        raw = yaml.safe_load(Path(path).read_text())
        kwargs: dict = dict(raw)
        if "workspace_root" in kwargs and isinstance(kwargs["workspace_root"], str):
            kwargs["workspace_root"] = Path(kwargs["workspace_root"])
        if "spec_file" in kwargs and isinstance(kwargs["spec_file"], str):
            kwargs["spec_file"] = Path(kwargs["spec_file"])
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
        return cls(**kwargs)

    @classmethod
    def from_yaml_or_default(cls, path: str | Path | None) -> FactoryConfig:
        if path is not None:
            p = Path(path)
            if p.exists():
                return cls.from_yaml(p)
        return cls()


def load_config(config_path: str | None) -> FactoryConfig:
    return FactoryConfig.from_yaml_or_default(config_path)
