from __future__ import annotations

from pathlib import Path

import pytest
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
        assert (
            config.dsn == "postgresql://substrate_test:substrate_test@localhost:5432/substrate_test"
        )
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


class TestConfigMalformed:
    def test_invalid_yaml_raises(self, tmp_path):
        yaml_path = tmp_path / "bad.yaml"
        yaml_path.write_text("workflow_name: broken\n  invalid_indent: true\n")
        with pytest.raises(yaml.error.YAMLError):
            FactoryConfig.from_yaml(yaml_path)

    def test_roles_dict_instead_of_list_raises(self, tmp_path):
        yaml_path = tmp_path / "roles_dict.yaml"
        yaml_path.write_text(yaml.dump({"roles": {"role": "impl", "channel": "kimi"}}))
        with pytest.raises(TypeError):
            FactoryConfig.from_yaml(yaml_path)

    def test_worker_roles_string_coerced_to_tuple(self, tmp_path):
        yaml_path = tmp_path / "roles_str.yaml"
        yaml_path.write_text(yaml.dump({"worker_roles": "interface_architect"}))
        config = FactoryConfig.from_yaml(yaml_path)
        assert isinstance(config.worker_roles, tuple)
        assert config.worker_roles == ("interface_architect",)

    def test_gate_roles_string_coerced_to_tuple(self, tmp_path):
        yaml_path = tmp_path / "gate_roles_str.yaml"
        yaml_path.write_text(yaml.dump({"gate_roles": "mechanical_gate"}))
        config = FactoryConfig.from_yaml(yaml_path)
        assert isinstance(config.gate_roles, tuple)
        assert config.gate_roles == ("mechanical_gate",)

    def test_missing_required_no_exception(self, tmp_path):
        # At the moment all fields have defaults, so missing fields are fine.
        yaml_path = tmp_path / "empty.yaml"
        yaml_path.write_text("{}")
        config = FactoryConfig.from_yaml(yaml_path)
        assert config.workflow_name == "software_factory"


class TestPhaseConfigRoundTrip:
    """Round-trip test: FactoryConfig.phaseN() -> dict -> YAML -> from_yaml().

    Catches YAML loader drift (e.g. missing stage_topology parsing, new
    fields not serialised) before it breaks a golden run.
    """

    def _plain_dict(self, config: FactoryConfig) -> dict:
        """Convert a frozen dataclass config to a plain dict with only
        JSON/YAML-safe types (lists instead of tuples, strings instead of Path).
        """

        def _convert(value: object) -> object:
            if isinstance(value, tuple):
                return [_convert(v) for v in value]
            if isinstance(value, list):
                return [_convert(v) for v in value]
            if isinstance(value, dict):
                return {k: _convert(v) for k, v in value.items()}
            if isinstance(value, Path):
                return str(value)
            # dataclass instances -> dict
            if hasattr(value, "__dataclass_fields__"):
                return {k: _convert(getattr(value, k)) for k in value.__dataclass_fields__}
            return value

        return _convert(config)  # type: ignore[return-value]

    def _roundtrip(self, config: FactoryConfig, tmp_path: Path) -> FactoryConfig:
        yaml_path = tmp_path / "config.yaml"
        yaml_path.write_text(yaml.dump(self._plain_dict(config)))
        return FactoryConfig.from_yaml(yaml_path)

    def test_phase2_roundtrip(self, tmp_path: Path):
        original = FactoryConfig.phase2()
        loaded = self._roundtrip(original, tmp_path)
        assert loaded.workflow_version == 2
        assert loaded.worker_roles == original.worker_roles
        assert loaded.type_to_role == original.type_to_role
        assert len(loaded.stage_topology) == 2
        assert loaded.stage_topology == original.stage_topology

    def test_phase3_roundtrip(self, tmp_path: Path):
        original = FactoryConfig.phase3()
        loaded = self._roundtrip(original, tmp_path)
        assert loaded.workflow_version == 3
        assert loaded.worker_roles == original.worker_roles
        assert loaded.type_to_role == original.type_to_role
        assert len(loaded.stage_topology) == 2
        assert loaded.stage_topology == original.stage_topology

    def test_phase4_roundtrip(self, tmp_path: Path):
        original = FactoryConfig.phase4()
        loaded = self._roundtrip(original, tmp_path)
        assert loaded.workflow_version == 4
        assert loaded.worker_roles == original.worker_roles
        assert loaded.type_to_role == original.type_to_role
        assert len(loaded.stage_topology) == 4
        assert loaded.stage_topology == original.stage_topology
        # review and jury handoffs are present
        types = {h.target_type for h in loaded.stage_topology}
        assert "review" in types
        assert "jury" in types

    def test_stage_topology_yaml_list(self, tmp_path: Path):
        """Direct YAML with stage_topology list round-trips correctly."""
        yaml_path = tmp_path / "config.yaml"
        yaml_path.write_text(
            yaml.dump(
                {
                    "stage_topology": [
                        {
                            "source_type": "interface_spec",
                            "source_state": "locked",
                            "target_type": "test_suite",
                            "link_type": "derived_from",
                            "ref_field": "interface_ref",
                        },
                        {
                            "source_type": "test_suite",
                            "source_state": "locked",
                            "target_type": "implementation",
                            "link_type": "tested_by",
                            "additional_links": ["implements"],
                            "ref_field": "test_suite_ref",
                            "propagate_fields": ["interface_ref"],
                        },
                        {
                            "source_type": "implementation",
                            "source_state": "locked",
                            "target_type": "review",
                            "link_type": "reviews",
                            "ref_field": "implementation_ref",
                            "propagate_fields": ["interface_ref", "test_suite_ref"],
                        },
                        {
                            "source_type": "review",
                            "source_state": "locked",
                            "target_type": "jury",
                            "link_type": "judges",
                            "ref_field": "review_ref",
                        },
                    ]
                }
            )
        )
        config = FactoryConfig.from_yaml(yaml_path)
        assert len(config.stage_topology) == 4
        assert config.stage_topology[2].target_type == "review"
        assert config.stage_topology[3].target_type == "jury"
        assert config.stage_topology[2].propagate_fields == (
            "interface_ref",
            "test_suite_ref",
        )
        assert config.stage_topology[1].additional_links == ("implements",)
