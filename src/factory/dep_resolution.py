from __future__ import annotations

import re
import uuid as _uuid
from dataclasses import dataclass
from pathlib import Path

from regista import Regista

from factory.constants import (
    CUSTOM_FIELD_ARTIFACT_PATH,
    CUSTOM_FIELD_INTERFACE_REF,
    CUSTOM_FIELD_MODULE_NAME,
    CUSTOM_FIELD_SPEC_SECTION,
    STATE_LOCKED,
    WORK_ITEM_TYPE_IMPLEMENTATION,
    WORK_ITEM_TYPE_INTERFACE_SPEC,
)


def _to_uuid(value: str | _uuid.UUID) -> _uuid.UUID:
    if isinstance(value, _uuid.UUID):
        return value
    return _uuid.UUID(value)


def _extract_module_name_from_spec(spec_section: str) -> str | None:
    m = re.search(r"^#\s*Interface Specification:\s*(.+)$", spec_section, re.MULTILINE)
    if m:
        title = m.group(1).strip()
        module_name = re.sub(r"[^a-zA-Z0-9_]", "_", title).lower()
        if not module_name.startswith("_"):
            return module_name
    return None


@dataclass(frozen=True)
class DepArtifact:
    module_name: str
    impl_path: Path | None
    spec_path: Path
    is_stub_only: bool


def _safe_artifact_path(raw: str | None) -> Path | None:
    if not raw:
        return None
    p = Path(raw)
    if ".." in p.parts:
        return None
    return p


def _validate_readable_path(p: Path) -> bool:
    if p.is_absolute():
        resolved = p.resolve()
        allowed_prefixes = ("/tmp/", "/var/tmp/", "/private/tmp/")
        return any(str(resolved).startswith(prefix) for prefix in allowed_prefixes)
    return True


def resolve_dep_artifacts(
    regista: Regista,
    dep_refs: list[str],
    page_size: int = 200,
) -> list[DepArtifact]:
    result: list[DepArtifact] = []
    for ref in dep_refs:
        ref_uuid = _to_uuid(ref)
        dep_wi = regista.get_work_item(ref_uuid)
        if not dep_wi or not dep_wi.custom_fields:
            continue
        module_name = dep_wi.custom_fields.get(CUSTOM_FIELD_MODULE_NAME) or None
        if not module_name:
            dep_spec = dep_wi.custom_fields.get(CUSTOM_FIELD_SPEC_SECTION, "")
            module_name = _extract_module_name_from_spec(dep_spec) if dep_spec else None
        spec_path = _safe_artifact_path(dep_wi.custom_fields.get(CUSTOM_FIELD_ARTIFACT_PATH))
        if spec_path is None or not spec_path.exists() or not _validate_readable_path(spec_path):
            continue
        if module_name is None:
            module_name = spec_path.stem

        impl_path: Path | None = None
        is_stub_only = True

        if dep_wi.work_item_type == WORK_ITEM_TYPE_INTERFACE_SPEC:
            impl_wi = _find_locked_impl(regista, str(ref_uuid), page_size=page_size)
            if impl_wi and impl_wi.custom_fields:
                raw_impl = impl_wi.custom_fields.get(CUSTOM_FIELD_ARTIFACT_PATH)
                impl_path = _safe_artifact_path(raw_impl)
                if impl_path and impl_path.exists() and _validate_readable_path(impl_path):
                    is_stub_only = False
        elif dep_wi.work_item_type == WORK_ITEM_TYPE_IMPLEMENTATION:
            if dep_wi.current_state == STATE_LOCKED:
                is_stub_only = False

        result.append(
            DepArtifact(
                module_name=module_name,
                impl_path=impl_path,
                spec_path=spec_path,
                is_stub_only=is_stub_only,
            )
        )
    return result


def _find_locked_impl(regista: Regista, spec_id: str, page_size: int = 200) -> object | None:
    impls = regista.query_work_items(
        work_item_types=[WORK_ITEM_TYPE_IMPLEMENTATION],
        current_states=[STATE_LOCKED],
        page_size=page_size,
    )
    for item in impls.items:
        custom = item.custom_fields or {}
        iface_ref = custom.get(CUSTOM_FIELD_INTERFACE_REF)
        if iface_ref and str(iface_ref) == str(spec_id):
            return item
    return None


def resolve_dep_refs_for_gate(
    regista: Regista,
    dep_refs: list[str],
) -> list[tuple[str, Path]]:
    dep_artifacts = resolve_dep_artifacts(regista, dep_refs)
    pairs: list[tuple[str, Path]] = []
    for dep in dep_artifacts:
        path = dep.impl_path if dep.impl_path else dep.spec_path
        pairs.append((dep.module_name, path))
    return pairs


def resolve_dep_refs_for_gate_rich(
    regista: Regista,
    dep_refs: list[str],
) -> list[tuple[str, Path, Path | None]]:
    dep_artifacts = resolve_dep_artifacts(regista, dep_refs)
    triples: list[tuple[str, Path, Path | None]] = []
    for dep in dep_artifacts:
        impl_path = dep.impl_path
        spec_path = dep.spec_path
        triples.append(
            (
                dep.module_name,
                impl_path if impl_path else spec_path,
                spec_path if impl_path else None,
            )
        )
    return triples


def resolve_dep_refs_for_context(
    regista: Regista,
    dep_refs: list[str],
) -> tuple[dict[str, str], list[str]]:
    dep_artifacts = resolve_dep_artifacts(regista, dep_refs)
    contents: dict[str, str] = {}
    stub_only: list[str] = []
    for dep in dep_artifacts:
        path = dep.impl_path if dep.impl_path else dep.spec_path
        contents[f"locked_dependency_{dep.module_name}"] = path.read_text()
        if dep.is_stub_only:
            stub_only.append(dep.module_name)
    return contents, stub_only
