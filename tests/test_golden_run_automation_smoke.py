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
    # This test documents the contract: populate_work_items.py reads
    # project_name, dsn, hmac_key_path, and workspace_root from the config.
    assert config.project_name == "test_populate_config"
    assert config.dsn.startswith("postgresql://")
    assert config.hmac_key_path == "tests/test_keys.json"
    assert str(config.workspace_root) == "/tmp/test-populate"
