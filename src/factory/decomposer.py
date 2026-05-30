from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import yaml


class DecomposerError(Exception):
    """Raised when deterministic decomposition encounters an error."""


AC_BOOT_ID = "AC-BOOT-01"

AC_BOOT_SPEC_SECTION = (
    "## AC-BOOT-01: Walking-skeleton boot\n"
    "\n"
    "Given a fresh environment, the assembled app starts, initializes its "
    "declared shared-state layer (DB schema / regista instance / …), "
    "and `GET /healthz` (or `/docs`) returns 200.\n"
)


def inject_boot_ac(spec_text: str) -> str:
    """Inject the canonical AC-BOOT-01 section into a substrate module spec.

    If the canonical section text (containing 'Walking-skeleton boot') is
    already present, return the spec unchanged.
    """
    if "Walking-skeleton boot" in spec_text:
        return spec_text
    return spec_text.rstrip("\n") + "\n\n" + AC_BOOT_SPEC_SECTION


@dataclass(frozen=True)
class DecomposedModule:
    module_name: str
    fr_id: str
    fr_text: str
    ac_entries: list[dict]
    dependency_fr_ids: list[str]
    glossary: dict[str, str]
    is_substrate: bool = False

    @property
    def ac_ids(self) -> list[str]:
        return [ac["id"] for ac in self.ac_entries]

    @property
    def dependency_names(self) -> list[str]:
        return [_fr_id_to_module_name(fr_id) for fr_id in self.dependency_fr_ids]

    @property
    def spec_text(self) -> str:
        return _render_module_spec(self)


@dataclass(frozen=True)
class DecompositionResult:
    source: str
    source_hash: str
    modules: list[DecomposedModule]
    glossary: dict[str, str]
    meta: dict


def decompose_from_spec_yaml(spec_yaml_path: Path) -> DecompositionResult:
    if not spec_yaml_path.exists():
        raise FileNotFoundError(f"spec.yaml not found: {spec_yaml_path}")
    raw = spec_yaml_path.read_text()
    source_hash = hashlib.sha256(raw.encode()).hexdigest()[:16]
    data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        raise ValueError(f"spec.yaml must be a mapping, got {type(data).__name__}")

    fr_map: dict[str, dict] = {}
    for fr in data.get("functional_requirements", []):
        fr_map[fr["id"]] = fr

    ac_by_fr: dict[str, list[dict]] = {}
    for ac in data.get("acceptance_criteria", []):
        for fr_id in ac.get("fr_ids", []):
            ac_by_fr.setdefault(fr_id, []).append(ac)

    dep_map: dict[str, list[str]] = {}
    for hint in _deep_get(data, "work_decomposition", "dependency_hints") or []:
        dep_map[hint["fr_id"]] = hint.get("requires", [])

    glossary = {}
    for entry in data.get("glossary", []):
        glossary[entry["term"]] = entry["definition"]

    modules: list[DecomposedModule] = []
    for fr_id, fr in sorted(fr_map.items()):
        dep_fr_ids = dep_map.get(fr_id, [])
        modules.append(
            DecomposedModule(
                module_name=_fr_id_to_module_name(fr_id),
                fr_id=fr_id,
                fr_text=fr.get("text", ""),
                ac_entries=ac_by_fr.get(fr_id, []),
                dependency_fr_ids=dep_fr_ids,
                glossary=glossary,
            )
        )

    meta = data.get("meta", {})
    return DecompositionResult(
        source=str(spec_yaml_path),
        source_hash=source_hash,
        modules=modules,
        glossary=glossary,
        meta=meta,
    )


def decompose_from_spec_md(spec_md_path: Path) -> DecompositionResult:
    if not spec_md_path.exists():
        raise FileNotFoundError(f"spec.md not found: {spec_md_path}")
    raw = spec_md_path.read_text()
    source_hash = hashlib.sha256(raw.encode()).hexdigest()[:16]

    fr_map = _parse_frs_from_md(raw)
    ac_by_fr = _parse_acs_from_md(raw)
    dep_map = _parse_deps_from_md(raw)
    glossary = _parse_glossary_from_md(raw)

    modules: list[DecomposedModule] = []
    for fr_id, fr_text in sorted(fr_map.items()):
        dep_fr_ids = dep_map.get(fr_id, [])
        modules.append(
            DecomposedModule(
                module_name=_fr_id_to_module_name(fr_id),
                fr_id=fr_id,
                fr_text=fr_text,
                ac_entries=ac_by_fr.get(fr_id, []),
                dependency_fr_ids=dep_fr_ids,
                glossary=glossary,
            )
        )

    return DecompositionResult(
        source=str(spec_md_path),
        source_hash=source_hash,
        modules=modules,
        glossary=glossary,
        meta={},
    )


def write_fixture_files(result: DecompositionResult, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for module in result.modules:
        path = output_dir / f"wi_{module.module_name}.md"
        path.write_text(module.spec_text)
        written.append(path)
    return written


def _fr_id_to_module_name(fr_id: str) -> str:
    return fr_id.lower().replace("-", "")


def _render_module_spec(module: DecomposedModule) -> str:
    lines: list[str] = []

    title = module.fr_id.replace("-", " ")
    lines.append(f"# Interface Specification: {title}")
    lines.append("")

    lines.append("## Dependencies")
    lines.append("")
    if module.dependency_names:
        for dep in sorted(module.dependency_names):
            lines.append(f"- `interface_ref`: `{dep}`")
    else:
        lines.append("None.")
    lines.append("")

    if module.glossary:
        lines.append("## Glossary")
        lines.append("")
        for term, definition in sorted(module.glossary.items()):
            lines.append(f"- **{term}**: {definition}")
        lines.append("")

    lines.append(f"## {module.fr_id}")
    lines.append("")
    lines.append(module.fr_text)
    lines.append("")

    for ac in module.ac_entries:
        ac_id = ac["id"]
        condition = ac.get("condition", ac.get("text", ""))
        # Skip AC-BOOT-01 from entries; it's injected by inject_boot_ac for substrate modules
        if ac_id == AC_BOOT_ID and module.is_substrate:
            continue
        if condition:
            lines.append(f"## {ac_id}")
            lines.append("")
            lines.append(condition)
            lines.append("")
        else:
            lines.append(f"## {ac_id}")
            lines.append("")

    output = "\n".join(lines)

    # Substrate modules always get the canonical boot AC injected
    if module.is_substrate:
        output = inject_boot_ac(output)

    return output


def _parse_frs_from_md(text: str) -> dict[str, str]:
    fr_map: dict[str, str] = {}
    pattern = r"^-?\s*(FR-(?:[A-Z]+-)?\d+)\s*(?:\*\*\[.*?\]\*\*)?\s*:\s*(.+)$"
    for m in re.finditer(pattern, text, re.MULTILINE):
        fr_map[m.group(1)] = m.group(2).strip()
    return fr_map


def _parse_acs_from_md(text: str) -> dict[str, list[dict]]:
    ac_by_fr: dict[str, list[dict]] = {}
    pattern = r"^-?\s*(AC-(?:[A-Z]+-)?\d+)\s*\[([^\]]+)\]\s*:\s*(.+)$"
    for m in re.finditer(pattern, text, re.MULTILINE):
        ac_id = m.group(1)
        fr_refs = m.group(2)
        condition = m.group(3).strip()
        for fr_match in re.finditer(r"FR-(?:[A-Z]+-)?\d+", fr_refs):
            ac_by_fr.setdefault(fr_match.group(0), []).append({"id": ac_id, "condition": condition})
    return ac_by_fr


def _parse_deps_from_md(text: str) -> dict[str, list[str]]:
    dep_map: dict[str, list[str]] = {}
    in_deps = False
    for line in text.splitlines():
        stripped = line.strip()
        _dep_heading = r"^#{1,3}\s+(implementation\s+phasing|dependency\s+hint)"
        if re.match(_dep_heading, stripped, re.IGNORECASE):
            in_deps = True
            continue
        if in_deps and stripped.startswith("#"):
            break
        if in_deps:
            m = re.match(r"^-?\s*(FR-(?:[A-Z]+-)?\d+)\s*:\s*(.+)$", stripped)
            if m:
                fr_id = m.group(1)
                dep_text = m.group(2)
                requires: list[str] = []
                for dep_match in re.finditer(r"FR-(?:[A-Z]+-)?\d+", dep_text):
                    requires.append(dep_match.group(0))
                dep_map[fr_id] = requires
    return dep_map


def _parse_glossary_from_md(text: str) -> dict[str, str]:
    glossary: dict[str, str] = {}
    in_glossary = False
    for line in text.splitlines():
        stripped = line.strip()
        if re.match(r"^#{1,3}\s+(\d+\.\s+)?glossary", stripped, re.IGNORECASE):
            in_glossary = True
            continue
        if in_glossary and stripped.startswith("#"):
            break
        if in_glossary and "|" in stripped and not stripped.startswith("|---"):
            cells = [c.strip() for c in stripped.split("|")]
            cells = [c for c in cells if c]
            if len(cells) >= 2 and cells[0] not in ("Term", "term"):
                glossary[cells[0]] = cells[1]
    return glossary


def _deep_get(data: dict, *keys: str) -> object:
    current: object = data
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
        else:
            return None
    return current
