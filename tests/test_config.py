from __future__ import annotations

from pathlib import Path

import yaml

from factory.config import FactoryConfig, RoleConfig


class TestFromYaml:
    def test_load_valid_yaml_all_fields(self, tmp_path):
        data = {
            "workflow_name": "custom_factory",
            "workflow_version": 2,
            "dsn": "postgresql://custom/custom_db",
            "hmac_key_path": "custom_keys.json",
            "project_name": "my_project",
            "workspace_root": str(tmp_path / "work"),
            "spec_file": str(tmp_path / "spec.md"),
            "poll_interval_seconds": 10,
            "claim_ttl_seconds": 600,
            "attempt_threshold": 5,
            "worker_roles": ["interface_architect", "test_author"],
            "gate_roles": ["mechanical_gate"],
            "type_to_role": [["interface_spec", "interface_architect"]],
            "roles": [
                {
                    "role": "interface_architect",
                    "channel": "claude-code",
                    "timeout_seconds": 300,
                },
                {
                    "role": "test_author",
                    "channel": "kimi",
                    "timeout_seconds": 120,
                },
            ],
        }
        yaml_path = tmp_path / "config.yaml"
        yaml_path.write_text(yaml.dump(data))

        config = FactoryConfig.from_yaml(yaml_path)
        assert config.workflow_name == "custom_factory"
        assert config.workflow_version == 2
        assert config.dsn == "postgresql://custom/custom_db"
        assert config.hmac_key_path == "custom_keys.json"
        assert config.project_name == "my_project"
        assert isinstance(config.workspace_root, Path)
        assert config.workspace_root == tmp_path / "work"
        assert isinstance(config.spec_file, Path)
        assert config.spec_file == tmp_path / "spec.md"
        assert config.poll_interval_seconds == 10
        assert config.claim_ttl_seconds == 600
        assert config.attempt_threshold == 5
        assert config.worker_roles == ("interface_architect", "test_author")
        assert config.gate_roles == ("mechanical_gate",)
        assert config.type_to_role == (("interface_spec", "interface_architect"),)
        assert len(config.roles) == 2
        assert config.roles[0] == RoleConfig("interface_architect", "claude-code", 300)
        assert config.roles[1] == RoleConfig("test_author", "kimi", 120)

    def test_missing_optional_fields_use_defaults(self, tmp_path):
        data = {"workflow_name": "minimal"}
        yaml_path = tmp_path / "minimal.yaml"
        yaml_path.write_text(yaml.dump(data))

        config = FactoryConfig.from_yaml(yaml_path)
        assert config.workflow_name == "minimal"
        assert config.workflow_version == 1
        assert config.workspace_root == Path(".factory/work")
        assert config.spec_file is None
        assert config.poll_interval_seconds == 5
        assert config.attempt_threshold == 3
        assert config.worker_roles == ("interface_architect",)

    def test_from_yaml_or_default_with_nonexistent_path(self, tmp_path):
        config = FactoryConfig.from_yaml_or_default(tmp_path / "does_not_exist.yaml")
        assert config.workflow_name == "software_factory"
        assert config.dsn == "postgresql://substrate_test:substrate_test@localhost:5432/substrate_test"
        assert config.workspace_root == Path(".factory/work")

    def test_from_yaml_or_default_with_existing_path(self, tmp_path):
        data = {"project_name": "override_project"}
        yaml_path = tmp_path / "override.yaml"
        yaml_path.write_text(yaml.dump(data))
        config = FactoryConfig.from_yaml_or_default(yaml_path)
        assert config.project_name == "override_project"

    def test_from_yaml_or_default_with_none(self):
        config = FactoryConfig.from_yaml_or_default(None)
        assert config.project_name == "sf2"

    def test_role_config_lookup(self, tmp_path):
        data = {
            "roles": [
                {"role": "implementer", "channel": "kimi", "timeout_seconds": 900},
            ],
        }
        yaml_path = tmp_path / "roles.yaml"
        yaml_path.write_text(yaml.dump(data))

        config = FactoryConfig.from_yaml(yaml_path)
        rc = config.get_role_config("implementer")
        assert rc is not None
        assert rc.channel == "kimi"
        assert rc.timeout_seconds == 900
        assert config.get_role_config("nonexistent") is None
