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
    CUSTOM_FIELD_INTEGRATION_REF,
    CUSTOM_FIELD_INTERFACE_REF,
    CUSTOM_FIELD_MODULE_NAME,
    CUSTOM_FIELD_REVIEW_FEEDBACK,
    CUSTOM_FIELD_REVIEW_REF,
    CUSTOM_FIELD_SPEC_SECTION,
    CUSTOM_FIELD_TEST_SUITE_REF,
    ROLE_CROSS_FAMILY_REVIEWER,
    ROLE_FRONTIER_JUDGE,
    ROLE_IMPLEMENTER,
    ROLE_INTEGRATOR,
    ROLE_OUTCOME_VERIFIER,
    ROLE_TEST_AUTHOR,
    STATE_LOCKED,
    WORK_ITEM_TYPE_IMPLEMENTATION,
    WORK_ITEM_TYPE_INTERFACE_SPEC,
)
from factory.dep_resolution import resolve_dep_refs_for_context
from factory.failure_summarizer import summarize_failures
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
    wi_id = _to_uuid(work_item_id)
    wi = substrate.get_work_item(wi_id)
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

    review_feedback = custom.get(CUSTOM_FIELD_REVIEW_FEEDBACK)
    if review_feedback:
        extra_artifacts["review_feedback"] = _format_review_feedback(review_feedback)

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


def derive_integrator_context(
    substrate: Substrate,
    work_item_id: str,
    spec_content: str | None = None,
    spec_glossary: dict[str, str] | None = None,
) -> PromptContext:
    """Derive context for the integrator role.

    Chases the work-item chain (integration -> jury -> review -> implementation)
    to inject the focal implementation, interface, and test suite. Also gathers
    ALL other locked implementations and interfaces in the project so the
    integrator can assemble the full module tree.
    """
    wi_id = _to_uuid(work_item_id)
    wi = substrate.get_work_item(wi_id)
    if wi is None:
        raise ValueError(f"Work item {work_item_id} not found")
    custom = wi.custom_fields or {}

    extra_artifacts: dict[str, str] = {}
    stub_only: list[str] = []
    export_map: dict[str, set[str]] = {}

    focal_impl_id: str | None = None

    integration_ref = custom.get(CUSTOM_FIELD_INTEGRATION_REF)
    if integration_ref:
        jury_wi = substrate.get_work_item(_to_uuid(integration_ref))
        if jury_wi and jury_wi.custom_fields:
            review_ref = jury_wi.custom_fields.get(CUSTOM_FIELD_REVIEW_REF)
            if review_ref:
                review_wi = substrate.get_work_item(_to_uuid(review_ref))
                if review_wi and review_wi.custom_fields:
                    review_custom = review_wi.custom_fields
                    focal_impl = _resolve_ref_artifact(
                        substrate, review_custom.get(CUSTOM_FIELD_IMPLEMENTATION_REF)
                    )
                    focal_iface = _resolve_ref_artifact(
                        substrate, review_custom.get(CUSTOM_FIELD_INTERFACE_REF)
                    )
                    focal_tests = _resolve_ref_artifact(
                        substrate, review_custom.get(CUSTOM_FIELD_TEST_SUITE_REF)
                    )
                    if focal_impl:
                        extra_artifacts["focal_implementation"] = focal_impl
                    if focal_iface:
                        extra_artifacts["focal_interface"] = focal_iface
                    if focal_tests:
                        extra_artifacts["focal_test_suite"] = focal_tests

                    impl_ref = review_custom.get(CUSTOM_FIELD_IMPLEMENTATION_REF)
                    if impl_ref:
                        focal_impl_id = str(impl_ref)
                        impl_wi = substrate.get_work_item(_to_uuid(impl_ref))
                        if impl_wi and impl_wi.custom_fields:
                            dep_contents, stub_only = _resolve_dependency_contents(
                                substrate, impl_wi.custom_fields
                            )
                            extra_artifacts.update(dep_contents)
                            export_map = _build_export_map_from_contents(dep_contents)

    other_impls, other_ifaces = _gather_other_locked_artifacts(substrate, focal_impl_id)
    for mod_name, source in other_impls.items():
        key = f"locked_impl_{mod_name}"
        if key not in extra_artifacts:
            extra_artifacts[key] = source
    for mod_name, source in other_ifaces.items():
        key = f"locked_iface_{mod_name}"
        if key not in extra_artifacts:
            extra_artifacts[key] = source

    return derive_context(
        substrate,
        work_item_id,
        role=ROLE_INTEGRATOR,
        spec_content=spec_content,
        spec_glossary=spec_glossary,
        extra_artifacts=extra_artifacts,
        stub_only_deps=stub_only,
        export_map=export_map,
    )


def _gather_other_locked_artifacts(
    substrate: Substrate,
    exclude_impl_id: str | None = None,
) -> tuple[dict[str, str], dict[str, str]]:
    """Gather all locked implementation and interface_spec artifacts
    across the project, excluding the focal implementation.

    Returns (impls_by_module_name, ifaces_by_module_name).
    """
    impls: dict[str, str] = {}
    ifaces: dict[str, str] = {}

    page = substrate.query_work_items(
        work_item_types=[WORK_ITEM_TYPE_IMPLEMENTATION],
        current_states=[STATE_LOCKED],
        page_size=200,
    )
    for item in page.items:
        item_id = str(item.work_item_id)
        if exclude_impl_id and item_id == exclude_impl_id:
            continue
        c = item.custom_fields or {}
        artifact_path = c.get(CUSTOM_FIELD_ARTIFACT_PATH)
        mod_name = c.get(CUSTOM_FIELD_MODULE_NAME, "")
        if not mod_name:
            mod_name = _infer_module_name_from_artifact_path(artifact_path)
        if artifact_path and mod_name:
            p = Path(artifact_path)
            if p.exists():
                impls[mod_name] = p.read_text()

    page = substrate.query_work_items(
        work_item_types=[WORK_ITEM_TYPE_INTERFACE_SPEC],
        current_states=[STATE_LOCKED],
        page_size=200,
    )
    for item in page.items:
        c = item.custom_fields or {}
        artifact_path = c.get(CUSTOM_FIELD_ARTIFACT_PATH)
        mod_name = c.get(CUSTOM_FIELD_MODULE_NAME, "")
        if not mod_name:
            mod_name = _infer_module_name_from_artifact_path(artifact_path)
        if artifact_path and mod_name:
            p = Path(artifact_path)
            if p.exists():
                ifaces[mod_name] = p.read_text()

    return impls, ifaces


def _infer_module_name_from_artifact_path(artifact_path: str | None) -> str:
    """Derive a module name from an artifact file path like
    /tmp/.../wi_XXX/ad/attempt-0001/certificate_model.pyi
    """
    if not artifact_path:
        return ""
    p = Path(artifact_path)
    stem = p.stem
    if stem and stem != "artifact":
        return stem
    parent = p.parent
    for part in reversed(parent.parts):
        if part.startswith("wi_"):
            return part.removeprefix("wi_")
    return ""


def derive_outcome_verifier_context(
    substrate: Substrate,
    work_item_id: str,
    spec_content: str | None = None,
    spec_glossary: dict[str, str] | None = None,
) -> PromptContext:
    """Derive context for the outcome_verifier role.

    Reads the integration artifact referenced by integration_ref and injects
    the assembled module tree and integration tests into the prompt.
    """
    wi_id = _to_uuid(work_item_id)
    wi = substrate.get_work_item(wi_id)
    if wi is None:
        raise ValueError(f"Work item {work_item_id} not found")
    custom = wi.custom_fields or {}

    extra_artifacts: dict[str, str] = {}
    integration_ref = custom.get(CUSTOM_FIELD_INTEGRATION_REF)
    if integration_ref:
        integration_wi = substrate.get_work_item(_to_uuid(integration_ref))
        if integration_wi and integration_wi.custom_fields:
            artifact_path = integration_wi.custom_fields.get(CUSTOM_FIELD_ARTIFACT_PATH)
            if artifact_path:
                p = Path(artifact_path)
                if p.exists():
                    try:
                        data = json.loads(p.read_text())
                    except Exception:
                        data = {}
                    assembled_tree = data.get("assembled_tree") or {}
                    for filename, source in assembled_tree.items():
                        extra_artifacts[f"assembled_module_{filename}"] = str(source)
                    integration_tests = data.get("integration_tests")
                    if integration_tests:
                        extra_artifacts["integration_tests"] = str(integration_tests)

    return derive_context(
        substrate,
        work_item_id,
        role=ROLE_OUTCOME_VERIFIER,
        spec_content=spec_content,
        spec_glossary=spec_glossary,
        extra_artifacts=extra_artifacts,
    )


def _format_review_feedback(raw: list[dict] | dict | str) -> str:
    """Render review feedback from gate-process custom_fields into a prompt section."""
    if isinstance(raw, str):
        return raw
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list):
        return str(raw)
    lines: list[str] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        severity = item.get("severity", "block")
        kind = item.get("kind", "impl")
        ac_id = item.get("ac_id", "")
        body = item.get("body", "")
        lines.append(f"- [{severity}] {ac_id} ({kind}): {body}")
    return "\n".join(lines)


def render_prompt(ctx: PromptContext) -> str:
    """Render a channel-ready prompt string from a PromptContext."""
    parts = [ctx.prompt_template, "", "---", ""]
    parts.append(f"work_item_id: {ctx.work_item_id}")
    parts.append(f"role: {ctx.role}")
    parts.append("")
    parts.append("## spec_section")
    parts.append("")
    parts.append("```")
    parts.append(ctx.spec_section)
    parts.append("```")
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
        summary = summarize_failures(ctx.prior_failures)
        if summary and len(ctx.prior_failures) >= 2:
            parts.append("## prior_failures (summarized)")
            parts.append("")
            parts.append(
                "Your previous attempts failed. These constraints are derived from the "
                "failure history. Each one identifies a concrete problem to avoid."
            )
            parts.append("")
            parts.append(summary.format_for_prompt())
        else:
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
        parts.append("```")
        parts.append(ctx.import_feedback)
        parts.append("```")
        parts.append("")
    if ctx.extra_artifacts:
        rendered_keys: set[str] = set()
        if "review_feedback" in ctx.extra_artifacts:
            parts.append("## review_feedback")
            parts.append("")
            parts.append(
                "A prior cross-family reviewer found the following defects in upstream artifacts. "
                "Address every block-severity finding before returning. "
                "Advise-severity findings are optional but improve quality."
            )
            parts.append("")
            parts.append("```")
            parts.append(ctx.extra_artifacts["review_feedback"])
            parts.append("```")
            parts.append("")
            rendered_keys.add("review_feedback")
        for key, value in sorted(ctx.extra_artifacts.items()):
            if key in rendered_keys:
                continue
            parts.append(f"## {key}")
            parts.append("")
            parts.append("```")
            parts.append(value)
            parts.append("```")
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
