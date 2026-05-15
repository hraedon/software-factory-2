from __future__ import annotations

from factory.config import FactoryConfig


class TestShouldUseProjectVenv:
    def test_default_none_without_requirements(self, tmp_path):
        cfg = FactoryConfig(workspace_root=tmp_path)
        assert cfg.should_use_project_venv() is False

    def test_default_none_with_requirements(self, tmp_path):
        (tmp_path / "requirements.txt").write_text("pytest\n")
        cfg = FactoryConfig(workspace_root=tmp_path)
        assert cfg.should_use_project_venv() is True

    def test_explicit_true(self, tmp_path):
        cfg = FactoryConfig(workspace_root=tmp_path, use_project_venv=True)
        assert cfg.should_use_project_venv() is True

    def test_explicit_false(self, tmp_path):
        (tmp_path / "requirements.txt").write_text("pytest\n")
        cfg = FactoryConfig(workspace_root=tmp_path, use_project_venv=False)
        assert cfg.should_use_project_venv() is False

    def test_from_yaml_auto_detect(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        (tmp_path / "requirements.txt").write_text("requests\n")
        config_file.write_text(f"workspace_root: '{tmp_path}'\nworkflow_version: 5\n")
        cfg = FactoryConfig.from_yaml(config_file)
        assert cfg.should_use_project_venv() is True

    def test_from_yaml_explicit_false(self, tmp_path):
        config_file = tmp_path / "config.yaml"
        (tmp_path / "requirements.txt").write_text("requests\n")
        config_file.write_text(
            f"workspace_root: '{tmp_path}'\nworkflow_version: 5\nuse_project_venv: false\n"
        )
        cfg = FactoryConfig.from_yaml(config_file)
        assert cfg.should_use_project_venv() is False
