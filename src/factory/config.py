from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RoleConfig:
    role: str
    channel: str
    timeout_seconds: int = 600


@dataclass(frozen=True)
class FactoryConfig:
    workflow_name: str = "software_factory"
    workflow_version: int = 1
    dsn: str = "postgresql://substrate_test:substrate_test@localhost:5432/substrate_test"
    hmac_key_path: str = "test_keys.json"
    project_name: str = "sf2"
    workspace_root: Path = Path(".factory/work")
    poll_interval_seconds: int = 5
    claim_ttl_seconds: int = 300
    worker_roles: tuple[str, ...] = ("interface_architect",)
    gate_roles: tuple[str, ...] = ("mechanical_gate",)
    roles: tuple[RoleConfig, ...] = (
        RoleConfig(role="interface_architect", channel="claude-code"),
        RoleConfig(role="mechanical_gate", channel="code"),
    )

    def get_role_config(self, role: str) -> RoleConfig | None:
        for rc in self.roles:
            if rc.role == role:
                return rc
        return None
