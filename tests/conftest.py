from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from substrate._testing import drop_project_schema
from substrate.testing import InMemorySubstrate

from factory.config import FactoryConfig

TESTS_DIR = Path(__file__).parent
DSN = "postgresql://substrate_test:substrate_test@localhost:5432/substrate_test"
KEY_PATH = str(TESTS_DIR / "test_keys.json")
WORKFLOW_PATH = str(Path(__file__).parent.parent / "workflows" / "phase1.yaml")
WORKFLOW_V2_PATH = str(Path(__file__).parent.parent / "workflows" / "phase2.yaml")
WORKFLOW_V5_PATH = str(Path(__file__).parent.parent / "workflows" / "phase5.yaml")


@pytest.fixture(scope="module")
def substrate():
    from substrate import Substrate

    project = f"sf2_test_{uuid.uuid4().hex[:8]}"
    sub = Substrate.create_project(DSN, project, KEY_PATH)
    sub.register_workflow_file(WORKFLOW_PATH)
    yield sub
    sub.close()
    drop_project_schema(DSN, project)


@pytest.fixture()
def factory_config(substrate, workspace_root):
    """Build a FactoryConfig using only public Substrate APIs."""
    return FactoryConfig(
        dsn=DSN,
        project_name=substrate.project,
        hmac_key_path=KEY_PATH,
        workspace_root=workspace_root,
    )


@pytest.fixture()
def mock_substrate():
    workflow_content = Path(WORKFLOW_PATH).read_text()
    sub = InMemorySubstrate()
    sub.register_workflow(workflow_content)
    yield sub
    sub.close()


@pytest.fixture(scope="module")
def phase5_substrate():
    from substrate import Substrate

    project = f"sf2_p5_{uuid.uuid4().hex[:8]}"
    sub = Substrate.create_project(DSN, project, KEY_PATH)
    sub.register_workflow_file(WORKFLOW_V5_PATH)
    yield sub
    sub.close()
    drop_project_schema(DSN, project)


@pytest.fixture()
def phase5_factory_config(phase5_substrate, workspace_root):
    """Build a FactoryConfig for Phase 5 using only public Substrate APIs."""
    return FactoryConfig(
        dsn=DSN,
        project_name=phase5_substrate.project,
        hmac_key_path=KEY_PATH,
        workspace_root=workspace_root,
    )


@pytest.fixture()
def mock_phase5_substrate():
    workflow_content = Path(WORKFLOW_V5_PATH).read_text()
    sub = InMemorySubstrate()
    sub.register_workflow(workflow_content)
    yield sub
    sub.close()


@pytest.fixture()
def workspace_root(tmp_path):
    return tmp_path / "factory" / "work"
