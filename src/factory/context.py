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
    CUSTOM_FIELD_IMPLEMENTATION_REF,
    CUSTOM_FIELD_INTERFACE_REF,
    CUSTOM_FIELD_REVIEW_REF,
    CUSTOM_FIELD_SPEC_SECTION,
    CUSTOM_FIELD_TEST_SUITE_REF,
    ROLE_CROSS_FAMILY_REVIEWER,
    ROLE_FRONTIER_JUDGE,
    ROLE_IMPLEMENTER,
    ROLE_TEST_AUTHOR,
)
from factory.dep_resolution import resolve_dep_refs_for_context
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
    stub_only_deps: list[str]
    export_map: dict[str, set[str]] | None = None
    import_feedback: str = ""


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
    stub_only_deps: list[str] | None = None,
    export_map: dict[str, set[str]] | None = None,
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
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt template not found: {prompt_path}")
    prompt_template = prompt_path.read_text()
    glossary = spec_glossary if spec_glossary is not None else {}
    section_content = spec_section
    if not section_content and spec_content is not None:
        section_content = spec_content
    extras = extra_artifacts or {}
    prompt_template_hash = hashlib.sha256(prompt_template.encode()).hexdigest()
    bundle = _serialize_bundle(
        section_content,
        ac_ids,
        glossary,
        failures,
        prompt_template,
        extras,
        stub_only_deps or [],
    )
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
        stub_only_deps=stub_only_deps or [],
        export_map=export_map,
    )


def _resolve_dependency_contents(
    substrate: Substrate,
    custom: dict,
) -> tuple[dict[str, str], list[str]]:
    dep_refs_raw = custom.get(CUSTOM_FIELD_DEPENDENCY_REFS) or []
    if isinstance(dep_refs_raw, str):
        dep_refs_raw = [dep_refs_raw]
    if not dep_refs_raw:
        return {}, []
    return resolve_dep_refs_for_context(substrate, dep_refs_raw)


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
    dep_contents, stub_only = _resolve_dependency_contents(substrate, custom)
    extra_artifacts.update(dep_contents)
    export_map = _build_export_map_from_contents(dep_contents)

    return derive_context(
        substrate,
        work_item_id,
        role=ROLE_TEST_AUTHOR,
        spec_content=spec_content,
        spec_glossary=spec_glossary,
        extra_artifacts=extra_artifacts,
        stub_only_deps=stub_only,
        export_map=export_map,
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
    dep_contents, stub_only = _resolve_dependency_contents(substrate, custom)
    extra_artifacts.update(dep_contents)
    export_map = _build_export_map_from_contents(dep_contents)

    return derive_context(
        substrate,
        work_item_id,
        role=ROLE_IMPLEMENTER,
        spec_content=spec_content,
        spec_glossary=spec_glossary,
        extra_artifacts=extra_artifacts,
        stub_only_deps=stub_only,
        export_map=export_map,
    )


def _resolve_ref_artifact(substrate: Substrate, ref: str | None) -> str:
    if not ref:
        return ""
    ref_wi = substrate.get_work_item(_to_uuid(ref))
    if ref_wi and ref_wi.custom_fields:
        ref_path = ref_wi.custom_fields.get(CUSTOM_FIELD_ARTIFACT_PATH)
        if ref_path:
            p = Path(ref_path)
            if p.exists():
                return p.read_text()
    return ""


def derive_review_context(
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

    locked_interface = _resolve_ref_artifact(substrate, custom.get(CUSTOM_FIELD_INTERFACE_REF))
    test_suite = _resolve_ref_artifact(substrate, custom.get(CUSTOM_FIELD_TEST_SUITE_REF))
    implementation = _resolve_ref_artifact(substrate, custom.get(CUSTOM_FIELD_IMPLEMENTATION_REF))

    extra_artifacts: dict[str, str] = {}
    if locked_interface:
        extra_artifacts["locked_interface"] = locked_interface
    if test_suite:
        extra_artifacts["test_suite"] = test_suite
    if implementation:
        extra_artifacts["implementation"] = implementation

    dep_contents, stub_only = _resolve_dependency_contents(substrate, custom)
    extra_artifacts.update(dep_contents)
    export_map = _build_export_map_from_contents(dep_contents)

    return derive_context(
        substrate,
        work_item_id,
        role=ROLE_CROSS_FAMILY_REVIEWER,
        spec_content=spec_content,
        spec_glossary=spec_glossary,
        extra_artifacts=extra_artifacts,
        stub_only_deps=stub_only,
        export_map=export_map,
    )


def derive_jury_context(
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

    review_ref = custom.get(CUSTOM_FIELD_REVIEW_REF)
    locked_interface = ""
    test_suite = ""
    implementation = ""
    if review_ref:
        review_wi = substrate.get_work_item(_to_uuid(review_ref))
        if review_wi and review_wi.custom_fields:
            review_custom = review_wi.custom_fields
            iface_ref = review_custom.get(CUSTOM_FIELD_INTERFACE_REF)
            ts_ref = review_custom.get(CUSTOM_FIELD_TEST_SUITE_REF)
            impl_ref = review_custom.get(CUSTOM_FIELD_IMPLEMENTATION_REF)
            locked_interface = _resolve_ref_artifact(substrate, iface_ref)
            test_suite = _resolve_ref_artifact(substrate, ts_ref)
            implementation = _resolve_ref_artifact(substrate, impl_ref)

    extra_artifacts: dict[str, str] = {}
    if locked_interface:
        extra_artifacts["locked_interface"] = locked_interface
    if test_suite:
        extra_artifacts["test_suite"] = test_suite
    if implementation:
        extra_artifacts["implementation"] = implementation

    dep_contents, stub_only = _resolve_dependency_contents(substrate, custom)
    extra_artifacts.update(dep_contents)
    export_map = _build_export_map_from_contents(dep_contents)

    return derive_context(
        substrate,
        work_item_id,
        role=ROLE_FRONTIER_JUDGE,
        spec_content=spec_content,
        spec_glossary=spec_glossary,
        extra_artifacts=extra_artifacts,
        stub_only_deps=stub_only,
        export_map=export_map,
    )


def _build_export_map_from_contents(
    dep_contents: dict[str, str],
) -> dict[str, set[str]]:
    from factory.gate import extract_exports

    export_map: dict[str, set[str]] = {}
    prefix = "locked_dependency_"
    for key, content in dep_contents.items():
        if key.startswith(prefix):
            module_name = key[len(prefix) :]
            try:
                export_map[module_name] = extract_exports(content)
            except Exception:
                pass
    return export_map


def _serialize_bundle(
    spec_section: str,
    ac_ids: list[str],
    glossary: dict[str, str],
    failures: list[FailureEntry],
    prompt_template: str,
    extra_artifacts: dict[str, str] | None = None,
    stub_only_deps: list[str] | None = None,
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
                "gate_output": f.gate_output,
            }
            for f in failures
        ],
        "prompt_template_hash": hashlib.sha256(prompt_template.encode()).hexdigest(),
    }
    if extra_artifacts:
        data["extra_artifacts"] = extra_artifacts
    if stub_only_deps:
        data["stub_only_deps"] = sorted(stub_only_deps)
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
            if f.gate_output:
                parts.append("  ```")
                for line in f.gate_output.splitlines():
                    parts.append(f"  {line}")
                parts.append("  ```")
        parts.append("")
    if ctx.import_feedback:
        parts.append("## import_resolution_feedback")
        parts.append("")
        parts.append(ctx.import_feedback)
        parts.append("")
    if ctx.extra_artifacts:
        for key, value in sorted(ctx.extra_artifacts.items()):
            parts.append(f"## {key}")
            parts.append("")
            parts.append(value)
            parts.append("")
    if ctx.export_map:
        parts.append("## available_dependency_imports")
        parts.append("")
        for module_name in sorted(ctx.export_map):
            symbols = sorted(ctx.export_map[module_name])
            is_stub = module_name in ctx.stub_only_deps
            tag = " (stub-only)" if is_stub else ""
            parts.append(f"- {module_name}{tag}: {', '.join(symbols)}")
        parts.append("")
    if ctx.stub_only_deps:
        parts.append("## stub_only_dependencies")
        parts.append("")
        parts.append(
            "WARNING: The following dependency modules are stub-only (interface_spec "
            "without a locked implementation). Their function bodies are Ellipsis (...). "
            "Do NOT call these functions at runtime — construct their return types directly."
        )
        for dep_name in sorted(ctx.stub_only_deps):
            parts.append(f"- {dep_name}")
        parts.append("")
    return "\n".join(parts)
