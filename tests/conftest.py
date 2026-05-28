from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from regista._testing import drop_project_schema
from regista.testing import InMemoryRegista

from factory.config import FactoryConfig

TESTS_DIR = Path(__file__).parent
DSN = "postgresql://regista_test:regista_test@localhost:5432/regista_test"
KEY_PATH = str(TESTS_DIR / "test_keys.json")
WORKFLOW_PATH = str(Path(__file__).parent.parent / "workflows" / "phase1.yaml")
WORKFLOW_V2_PATH = str(Path(__file__).parent.parent / "workflows" / "phase2.yaml")
WORKFLOW_V5_PATH = str(Path(__file__).parent.parent / "workflows" / "phase5.yaml")


@pytest.fixture(scope="module")
def regista():
    from regista import Regista

    project = f"sf2_test_{uuid.uuid4().hex[:8]}"
    sub = Regista.create_project(DSN, project, KEY_PATH)
    sub.register_workflow_file(WORKFLOW_PATH)
    yield sub
    sub.close()
    drop_project_schema(DSN, project)


@pytest.fixture()
def factory_config(regista, workspace_root):
    """Build a FactoryConfig using only public Regista APIs."""
    return FactoryConfig(
        dsn=DSN,
        project_name=regista.project,
        hmac_key_path=KEY_PATH,
        workspace_root=workspace_root,
    )


@pytest.fixture()
def mock_regista():
    sub = InMemoryRegista()
    sub.register_workflow_file(WORKFLOW_PATH)
    yield sub
    sub.close()


@pytest.fixture(scope="module")
def phase5_regista():
    from regista import Regista

    project = f"sf2_p5_{uuid.uuid4().hex[:8]}"
    sub = Regista.create_project(DSN, project, KEY_PATH)
    sub.register_workflow_file(WORKFLOW_V5_PATH)
    yield sub
    sub.close()
    drop_project_schema(DSN, project)


@pytest.fixture()
def phase5_factory_config(phase5_regista, workspace_root):
    """Build a FactoryConfig for Phase 5 using only public Regista APIs."""
    return FactoryConfig(
        dsn=DSN,
        project_name=phase5_regista.project,
        hmac_key_path=KEY_PATH,
        workspace_root=workspace_root,
    )


@pytest.fixture()
def mock_phase5_regista():
    sub = InMemoryRegista()
    sub.register_workflow_file(WORKFLOW_V5_PATH)
    yield sub
    sub.close()


@pytest.fixture()
def workspace_root(tmp_path):
    return tmp_path / "factory" / "work"
