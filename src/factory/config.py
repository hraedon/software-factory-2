from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class RoleConfig:
    role: str
    channel: str
    timeout_seconds: int = 600


_DEFAULT_WORKSPACE = Path(".factory/work")


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
    worker_roles: tuple[str, ...] = ("interface_architect",)
    gate_roles: tuple[str, ...] = ("mechanical_gate",)
    type_to_role: tuple[tuple[str, str], ...] = (("interface_spec", "interface_architect"),)
    roles: tuple[RoleConfig, ...] = (
        RoleConfig(role="interface_architect", channel="claude-code"),
        RoleConfig(role="mechanical_gate", channel="code"),
    )

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
        if "roles" in kwargs and isinstance(kwargs["roles"], list):
            kwargs["roles"] = tuple(RoleConfig(**r) for r in kwargs["roles"])
        if "worker_roles" in kwargs and isinstance(kwargs["worker_roles"], list):
            kwargs["worker_roles"] = tuple(kwargs["worker_roles"])
        if "gate_roles" in kwargs and isinstance(kwargs["gate_roles"], list):
            kwargs["gate_roles"] = tuple(kwargs["gate_roles"])
        if "type_to_role" in kwargs and isinstance(kwargs["type_to_role"], list):
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
