from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from substrate import Substrate

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


def derive_context(
    substrate: Substrate,
    work_item_id: str,
    role: str,
    spec_content: str | None = None,
    spec_glossary: dict[str, str] | None = None,
) -> PromptContext:
    wi = substrate.get_work_item(work_item_id)
    if wi is None:
        raise ValueError(f"Work item {work_item_id} not found")
    custom = wi.custom_fields or {}
    spec_section = custom.get("spec_section", "")
    ac_ids_raw = custom.get("ac_ids", [])
    ac_ids = ac_ids_raw if isinstance(ac_ids_raw, list) else [ac_ids_raw]
    failures = derive_failures(substrate, work_item_id)
    prompt_path = PROMPTS_DIR / f"{role}.md"
    prompt_template = prompt_path.read_text() if prompt_path.exists() else ""
    glossary = spec_glossary if spec_glossary is not None else {}
    section_content = spec_content if spec_content is not None else spec_section
    bundle = _serialize_bundle(section_content, ac_ids, glossary, failures, prompt_template)
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
    )


def _serialize_bundle(
    spec_section: str,
    ac_ids: list[str],
    glossary: dict[str, str],
    failures: list[FailureEntry],
    prompt_template: str,
) -> str:
    data = {
        "spec_section": spec_section,
        "ac_ids": sorted(ac_ids),
        "glossary": dict(sorted(glossary.items())),
        "prior_failures": [
            {
                "attempt_number": f.attempt_number,
                "role": f.role,
                "channel": f.channel,
                "gate_name": f.gate_name,
                "diagnostic": f.diagnostic,
            }
            for f in failures
        ],
        "prompt_template_hash": hashlib.sha256(prompt_template.encode()).hexdigest(),
    }
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
    return "\n".join(parts)
