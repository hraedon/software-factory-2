from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

_catalog_log = logging.getLogger("factory.catalog")

_CATALOG_DIR = Path(__file__).parent.parent.parent / "catalog"
_PLACEHOLDER_RE = re.compile(r"\{(\w+)\}")

_DEFAULT_ARCHETYPE = "cli-tool"


@dataclass(frozen=True)
class Archetype:
    name: str
    version: int
    compatible_phases: list[int]
    required_roles: list[str]
    dependencies: list[str]
    entry_point: str
    test_pattern: str
    skeleton_dir: Path
    prompt_addendum: str


def load_archetype(name: str, catalog_dir: Path | None = None) -> Archetype:
    base = catalog_dir or _CATALOG_DIR
    arch_dir = base / name
    if not arch_dir.exists():
        raise FileNotFoundError(f"Archetype '{name}' not found in {base}")

    meta_path = arch_dir / "archetype.yaml"
    if not meta_path.exists():
        raise FileNotFoundError(f"archetype.yaml not found in {arch_dir}")

    meta = yaml.safe_load(meta_path.read_text())
    addendum_path = arch_dir / "prompt_addendum.md"
    prompt_addendum = addendum_path.read_text() if addendum_path.exists() else ""

    return Archetype(
        name=meta["name"],
        version=meta.get("version", 1),
        compatible_phases=meta.get("compatible_phases", []),
        required_roles=meta.get("required_roles", []),
        dependencies=meta.get("dependencies", []),
        entry_point=meta.get("entry_point", ""),
        test_pattern=meta.get("test_pattern", ""),
        skeleton_dir=arch_dir / "skeleton",
        prompt_addendum=prompt_addendum,
    )


def list_archetypes(catalog_dir: Path | None = None) -> list[str]:
    base = catalog_dir or _CATALOG_DIR
    if not base.exists():
        return []
    return sorted(d.name for d in base.iterdir() if d.is_dir() and (d / "archetype.yaml").exists())


def apply_skeleton(
    archetype: Archetype,
    target_dir: Path,
    project_name: str,
    module_name: str | None = None,
) -> list[Path]:
    mod = module_name or project_name
    skeleton = archetype.skeleton_dir
    if not skeleton.exists():
        return []

    created: list[Path] = []
    for source_path in skeleton.rglob("*"):
        if source_path.is_dir():
            continue
        relative = source_path.relative_to(skeleton)
        target = target_dir / str(relative)

        content = source_path.read_text()
        content = content.replace("{project_name}", project_name)
        content = content.replace("{module_name}", mod)

        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        created.append(target)

    _catalog_log.info(
        "skeleton_applied archetype=%s target=%s files=%d",
        archetype.name,
        target_dir,
        len(created),
    )
    return created


def validate_archetype(
    archetype: Archetype, config_phases: list[int], config_roles: list[str]
) -> list[str]:
    warnings: list[str] = []
    if archetype.compatible_phases:
        if not any(p in archetype.compatible_phases for p in config_phases):
            warnings.append(
                f"Archetype '{archetype.name}' not compatible "
                f"with configured phases {config_phases}"
            )
    missing = set(archetype.required_roles) - set(config_roles)
    if missing:
        warnings.append(
            f"Archetype '{archetype.name}' requires roles {sorted(missing)} not in config"
        )
    return warnings
