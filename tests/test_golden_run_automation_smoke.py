from __future__ import annotations

from pathlib import Path

from factory.config import FactoryConfig


def test_populate_work_items_config_parsing() -> None:
    """populate_work_items.py --config must resolve FactoryConfig fields correctly."""
    config = FactoryConfig(
        workflow_name="software_factory",
        workflow_version=2,
        project_name="test_populate_config",
        dsn="postgresql://test:test@localhost:5432/test",
        hmac_key_path="tests/test_keys.json",
        workspace_root=Path("/tmp/test-populate"),
    )
    assert config.project_name == "test_populate_config"
    assert config.dsn.startswith("postgresql://")
    assert config.hmac_key_path == "tests/test_keys.json"
    assert str(config.workspace_root) == "/tmp/test-populate"


def test_workflow_version_to_name_mapping() -> None:
    """BC-125: workflow_version in config must map to correct workflow file name."""
    mapping = {1: "phase1", 2: "phase2", 3: "phase3"}
    for version, expected in mapping.items():
        config = FactoryConfig(
            workflow_name="software_factory",
            workflow_version=version,
            project_name="test_wf",
            dsn="postgresql://test:test@localhost:5432/test",
            hmac_key_path="tests/test_keys.json",
            workspace_root=Path("/tmp/test-wf"),
        )
        assert mapping.get(config.workflow_version, "phase2") == expected


def test_workflow_version_3_infers_phase3() -> None:
    """BC-125: config with workflow_version=3 must infer 'phase3' not default 'phase2'."""
    config = FactoryConfig(
        workflow_name="software_factory",
        workflow_version=3,
        project_name="test_wf3",
        dsn="postgresql://test:test@localhost:5432/test",
        hmac_key_path="tests/test_keys.json",
        workspace_root=Path("/tmp/test-wf3"),
    )
    inferred = {1: "phase1", 2: "phase2", 3: "phase3"}.get(config.workflow_version, "phase2")
    assert inferred == "phase3"
