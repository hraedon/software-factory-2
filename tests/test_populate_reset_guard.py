from __future__ import annotations

import pytest

from populate_work_items import _validate_workspace_root_for_reset


class TestWorkspaceResetGuard:
    def test_tmp_path_allowed(self):
        _validate_workspace_root_for_reset("/tmp/sf2-golden-run")

    def test_project_root_allowed(self, tmp_path):
        import populate_work_items

        project_path = tmp_path / "my-project"
        project_path.mkdir()
        orig = populate_work_items.ROOT_DIR
        try:
            populate_work_items.ROOT_DIR = project_path
            _validate_workspace_root_for_reset(project_path / "subdir")
        finally:
            populate_work_items.ROOT_DIR = orig

    def test_home_directory_rejected(self):
        with pytest.raises(ValueError, match=r"Refusing to delete"):
            _validate_workspace_root_for_reset("/home/user/projects")

    def test_dotdot_rejected(self):
        with pytest.raises(ValueError, match=r"\.\."):
            _validate_workspace_root_for_reset("/tmp/../etc/passwd")

    def test_var_tmp_allowed(self):
        _validate_workspace_root_for_reset("/var/tmp/sf2-workspace")
