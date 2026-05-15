from __future__ import annotations

import pytest

from factory.catalog import (
    Archetype,
    apply_skeleton,
    list_archetypes,
    load_archetype,
    validate_archetype,
)


class TestListArchetypes:
    def test_lists_builtin_archetypes(self):
        archetypes = list_archetypes()
        assert "cli-tool" in archetypes
        assert "web-service" in archetypes
        assert "library-module" in archetypes

    def test_nonexistent_dir(self, tmp_path):
        archetypes = list_archetypes(tmp_path / "nonexistent")
        assert archetypes == []


class TestLoadArchetype:
    def test_loads_cli_tool(self):
        arch = load_archetype("cli-tool")
        assert arch.name == "cli-tool"
        assert arch.version == 1
        assert "interface_architect" in arch.required_roles
        assert arch.entry_point == "src/{module_name}/cli.py"
        assert arch.skeleton_dir.exists()
        assert len(arch.prompt_addendum) > 0

    def test_loads_web_service(self):
        arch = load_archetype("web-service")
        assert arch.name == "web-service"

    def test_loads_library_module(self):
        arch = load_archetype("library-module")
        assert arch.name == "library-module"
        assert arch.entry_point == ""

    def test_nonexistent_archetype(self):
        with pytest.raises(FileNotFoundError, match="not-found"):
            load_archetype("not-found")

    def test_custom_catalog_dir(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_archetype("cli-tool", catalog_dir=tmp_path)


class TestApplySkeleton:
    def test_copies_files_with_substitution(self, tmp_path):
        arch = load_archetype("cli-tool")
        target = tmp_path / "workspace"
        target.mkdir()
        created = apply_skeleton(arch, target, "mytool", "mytool")
        assert len(created) > 0
        assert (target / "pyproject.toml").exists()
        content = (target / "pyproject.toml").read_text()
        assert "mytool" in content
        assert (target / "README.md").exists()
        readme = (target / "README.md").read_text()
        assert "mytool" in readme

    def test_substitutes_module_name(self, tmp_path):
        arch = load_archetype("cli-tool")
        target = tmp_path / "workspace"
        target.mkdir()
        apply_skeleton(arch, target, "my-project", "my_module")
        pyproject = (target / "pyproject.toml").read_text()
        assert "my-project" in pyproject

    def test_empty_skeleton(self, tmp_path):
        arch_dir = tmp_path / "empty-arch" / "skeleton"
        arch_dir.mkdir(parents=True)
        meta_dir = tmp_path / "empty-arch"
        (meta_dir / "archetype.yaml").write_text("name: empty\nversion: 1\n")
        arch = Archetype(
            name="empty",
            version=1,
            compatible_phases=[],
            required_roles=[],
            dependencies=[],
            entry_point="",
            test_pattern="",
            skeleton_dir=arch_dir,
            prompt_addendum="",
        )
        target = tmp_path / "target"
        target.mkdir()
        created = apply_skeleton(arch, target, "test")
        assert created == []


class TestValidateArchetype:
    def test_valid_archetype(self):
        arch = load_archetype("cli-tool")
        warnings = validate_archetype(
            arch,
            config_phases=[5],
            config_roles=["interface_architect", "test_author", "implementer"],
        )
        assert warnings == []

    def test_missing_role(self):
        arch = load_archetype("cli-tool")
        warnings = validate_archetype(
            arch,
            config_phases=[5],
            config_roles=["interface_architect"],
        )
        assert len(warnings) == 1
        assert "test_author" in warnings[0]

    def test_incompatible_phase(self):
        arch = load_archetype("cli-tool")
        warnings = validate_archetype(
            arch,
            config_phases=[99],
            config_roles=["interface_architect", "test_author", "implementer"],
        )
        assert len(warnings) == 1
        assert "compatible" in warnings[0]
