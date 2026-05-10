from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from substrate import Substrate

from factory.constants import (
    CUSTOM_FIELD_AC_IDS,
    CUSTOM_FIELD_ARTIFACT_PATH,
    CUSTOM_FIELD_DEPENDENCY_REFS,
    CUSTOM_FIELD_INTERFACE_REF,
    CUSTOM_FIELD_SPEC_SECTION,
    CUSTOM_FIELD_TEST_SUITE_REF,
    ROLE_IMPLEMENTER,
    ROLE_TEST_AUTHOR,
)
from factory.failure_summary import FailureEntry, derive_failures

PROMPTS_DIR = Path(__file__).parent / "prompts"


@dataclass(frozen=True)
class PromptContext:
    work_item_id: str
    role: str
    spec_section: str
    ac_ids: list[str]
    glossary: dict[str, str]
    prior_failures: list[FailureEntry]
    prompt_template: str
    context_hash: str
    prompt_template_hash: str
    extra_artifacts: dict[str, str]


def _to_uuid(value: str | uuid.UUID) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    return uuid.UUID(value)


def derive_context(
    substrate: Substrate,
    work_item_id: str,
    role: str,
    spec_content: str | None = None,
    spec_glossary: dict[str, str] | None = None,
    extra_artifacts: dict[str, str] | None = None,
) -> PromptContext:
    wi = substrate.get_work_item(work_item_id)
    if wi is None:
        raise ValueError(f"Work item {work_item_id} not found")
    custom = wi.custom_fields or {}
    spec_section = custom.get(CUSTOM_FIELD_SPEC_SECTION, "")
    ac_ids_raw = custom.get(CUSTOM_FIELD_AC_IDS, [])
    ac_ids = ac_ids_raw if isinstance(ac_ids_raw, list) else [ac_ids_raw]
    failures = derive_failures(substrate, work_item_id)
    prompt_path = PROMPTS_DIR / f"{role}.md"
    prompt_template = prompt_path.read_text() if prompt_path.exists() else ""
    glossary = spec_glossary if spec_glossary is not None else {}
    section_content = spec_section
    if not section_content and spec_content is not None:
        section_content = spec_content
    extras = extra_artifacts or {}
    prompt_template_hash = hashlib.sha256(prompt_template.encode()).hexdigest()
    bundle = _serialize_bundle(section_content, ac_ids, glossary, failures, prompt_template, extras)
    context_hash = hashlib.sha256(bundle.encode()).hexdigest()
    return PromptContext(
        work_item_id=str(work_item_id),
        role=role,
        spec_section=section_content,
        ac_ids=ac_ids,
        glossary=glossary,
        prior_failures=failures,
        prompt_template=prompt_template,
        context_hash=context_hash,
        prompt_template_hash=prompt_template_hash,
        extra_artifacts=extras,
    )


def _resolve_dependency_contents(substrate: Substrate, custom: dict) -> dict[str, str]:
    dep_refs_raw = custom.get(CUSTOM_FIELD_DEPENDENCY_REFS) or []
    if isinstance(dep_refs_raw, str):
        dep_refs_raw = [dep_refs_raw]
    contents: dict[str, str] = {}
    for ref in dep_refs_raw:
        ref_wi = substrate.get_work_item(_to_uuid(ref))
        if not ref_wi or not ref_wi.custom_fields:
            continue
        ref_path = ref_wi.custom_fields.get(CUSTOM_FIELD_ARTIFACT_PATH)
        if not ref_path:
            continue
        p = Path(ref_path)
        if not p.exists():
            continue
        dep_spec = ref_wi.custom_fields.get(CUSTOM_FIELD_SPEC_SECTION, "")
        module_name = _extract_module_name_from_spec(dep_spec) if dep_spec else None
        if module_name is None:
            module_name = p.stem
        contents[f"locked_dependency_{module_name}"] = p.read_text()
    return contents


def _extract_module_name_from_spec(spec_section: str) -> str | None:
    import re

    m = re.search(r"^#\s*Interface Specification:\s*(.+)$", spec_section, re.MULTILINE)
    if m:
        title = m.group(1).strip()
        module_name = re.sub(r"[^a-zA-Z0-9_]", "_", title).lower()
        if not module_name.startswith("_"):
            return module_name
    return None


def derive_test_author_context(
    substrate: Substrate,
    work_item_id: str,
    spec_content: str | None = None,
    spec_glossary: dict[str, str] | None = None,
) -> PromptContext:
    wi_id = _to_uuid(work_item_id)
    wi = substrate.get_work_item(wi_id)
    if wi is None:
        raise ValueError(f"Work item {work_item_id} not found")
    custom = wi.custom_fields or {}

    interface_ref = custom.get(CUSTOM_FIELD_INTERFACE_REF)
    locked_interface = ""
    if interface_ref:
        ref_wi = substrate.get_work_item(_to_uuid(interface_ref))
        if ref_wi and ref_wi.custom_fields:
            ref_path = ref_wi.custom_fields.get(CUSTOM_FIELD_ARTIFACT_PATH)
            if ref_path:
                p = Path(ref_path)
                if p.exists():
                    locked_interface = p.read_text()

    extra_artifacts = {}
    if locked_interface:
        extra_artifacts["locked_interface"] = locked_interface
    dep_contents = _resolve_dependency_contents(substrate, custom)
    extra_artifacts.update(dep_contents)

    return derive_context(
        substrate,
        work_item_id,
        role=ROLE_TEST_AUTHOR,
        spec_content=spec_content,
        spec_glossary=spec_glossary,
        extra_artifacts=extra_artifacts,
    )


def derive_implementer_context(
    substrate: Substrate,
    work_item_id: str,
    spec_content: str | None = None,
    spec_glossary: dict[str, str] | None = None,
) -> PromptContext:
    wi_id = _to_uuid(work_item_id)
    wi = substrate.get_work_item(wi_id)
    if wi is None:
        raise ValueError(f"Work item {work_item_id} not found")
    custom = wi.custom_fields or {}

    interface_ref = custom.get(CUSTOM_FIELD_INTERFACE_REF)
    test_suite_ref = custom.get(CUSTOM_FIELD_TEST_SUITE_REF)

    locked_interface = ""
    test_suite = ""

    if interface_ref:
        ref_wi = substrate.get_work_item(_to_uuid(interface_ref))
        if ref_wi and ref_wi.custom_fields:
            ref_path = ref_wi.custom_fields.get(CUSTOM_FIELD_ARTIFACT_PATH)
            if ref_path:
                p = Path(ref_path)
                if p.exists():
                    locked_interface = p.read_text()

    if test_suite_ref:
        ref_wi = substrate.get_work_item(_to_uuid(test_suite_ref))
        if ref_wi and ref_wi.custom_fields:
            ref_path = ref_wi.custom_fields.get(CUSTOM_FIELD_ARTIFACT_PATH)
            if ref_path:
                p = Path(ref_path)
                if p.exists():
                    test_suite = p.read_text()

    extra_artifacts = {}
    if locked_interface:
        extra_artifacts["locked_interface"] = locked_interface
    if test_suite:
        extra_artifacts["test_suite"] = test_suite
    dep_contents = _resolve_dependency_contents(substrate, custom)
    extra_artifacts.update(dep_contents)

    return derive_context(
        substrate,
        work_item_id,
        role=ROLE_IMPLEMENTER,
        spec_content=spec_content,
        spec_glossary=spec_glossary,
        extra_artifacts=extra_artifacts,
    )


def _serialize_bundle(
    spec_section: str,
    ac_ids: list[str],
    glossary: dict[str, str],
    failures: list[FailureEntry],
    prompt_template: str,
    extra_artifacts: dict[str, str] | None = None,
) -> str:
    data: dict[str, Any] = {
        "spec_section": spec_section,
        "ac_ids": sorted(ac_ids),
        "glossary": dict(sorted(glossary.items())),
        "prior_failures": [
            {
                "attempt_number": f.attempt_number,
                "role": f.role,
                "channel": f.channel,
                "failure_type": f.failure_type,
                "gate_name": f.gate_name,
                "diagnostic": f.diagnostic,
                "error_message": f.error_message,
                "timed_out": f.timed_out,
            }
            for f in failures
        ],
        "prompt_template_hash": hashlib.sha256(prompt_template.encode()).hexdigest(),
    }
    if extra_artifacts:
        data["extra_artifacts"] = extra_artifacts
    return json.dumps(data, sort_keys=True)


def render_prompt(ctx: PromptContext) -> str:
    """Render a channel-ready prompt string from a PromptContext."""
    parts = [ctx.prompt_template, "", "---", ""]
    parts.append(f"work_item_id: {ctx.work_item_id}")
    parts.append(f"role: {ctx.role}")
    parts.append("")
    parts.append("## spec_section")
    parts.append("")
    parts.append(ctx.spec_section)
    parts.append("")
    parts.append("## ac_ids")
    parts.append("")
    for ac_id in ctx.ac_ids:
        parts.append(f"- {ac_id}")
    parts.append("")
    if ctx.glossary:
        parts.append("## glossary")
        parts.append("")
        for term, definition in sorted(ctx.glossary.items()):
            parts.append(f"- **{term}**: {definition}")
        parts.append("")
    if ctx.prior_failures:
        parts.append("## prior_failures")
        parts.append("")
        for f in ctx.prior_failures:
            parts.append(
                f"- attempt {f.attempt_number} ({f.role}/{f.channel}): "
                f"{f.gate_name} — {f.diagnostic}"
            )
        parts.append("")
    if ctx.extra_artifacts:
        for key, value in sorted(ctx.extra_artifacts.items()):
            parts.append(f"## {key}")
            parts.append("")
            parts.append(value)
            parts.append("")
    return "\n".join(parts)
