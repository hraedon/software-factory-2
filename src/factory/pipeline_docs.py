from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from substrate import compose_workflow

from factory.router import _ESCALATABLE_KINDS, _KIND_DISPATCH, DiagnosticKind

WORKFLOWS_DIR = Path(__file__).parent.parent.parent / "workflows"
PROMPTS_DIR = Path(__file__).parent / "prompts"


def _load_workflow_yaml(path: Path) -> dict:
    composed, _ = compose_workflow(path)
    return composed


@dataclass
class PipelineDoc:
    workflow_version: int = 0
    states: list[str] = field(default_factory=list)
    work_item_types: list[str] = field(default_factory=list)
    roles: list[str] = field(default_factory=list)
    stage_handoffs: list[str] = field(default_factory=list)
    failure_routes: list[str] = field(default_factory=list)
    escalatable_kinds: list[str] = field(default_factory=list)
    custom_fields: dict[str, list[str]] = field(default_factory=dict)
    link_types: list[str] = field(default_factory=list)


def generate_from_workflow(workflow_path: Path) -> PipelineDoc:
    data = _load_workflow_yaml(workflow_path)
    doc = PipelineDoc()
    doc.workflow_version = data.get("version", 0)

    states = set()
    for state_def in data.get("states", []):
        if isinstance(state_def, str):
            states.add(state_def)
        elif isinstance(state_def, dict):
            states.add(state_def.get("name", ""))
    doc.states = sorted(states)

    doc.work_item_types = [
        wit.get("name", "") if isinstance(wit, dict) else str(wit)
        for wit in data.get("work_item_types", [])
    ]

    doc.roles = sorted(
        r.get("name", "") if isinstance(r, dict) else str(r) for r in data.get("roles", [])
    )

    doc.link_types = sorted(
        lt.get("name", "") if isinstance(lt, dict) else str(lt) for lt in data.get("link_types", [])
    )

    for wit_def in data.get("work_item_types", []):
        if not isinstance(wit_def, dict):
            continue
        name = wit_def.get("name", "")
        cf_list = wit_def.get("custom_fields", [])
        fields = []
        for cf in cf_list:
            if isinstance(cf, dict):
                fields.append(cf.get("name", ""))
            else:
                fields.append(str(cf))
        if fields:
            doc.custom_fields[name] = sorted(fields)

    for transition_def in data.get("transitions", []):
        if isinstance(transition_def, dict):
            from_state = transition_def.get("from", "")
            to_state = transition_def.get("to", "")
            name = transition_def.get("name", "")
            allowed = transition_def.get("allowed_roles", [])
            role_str = ", ".join(allowed) if allowed else "any"
            doc.stage_handoffs.append(f"{from_state} → {to_state} ({name}: {role_str})")

    return doc


def generate_router_table() -> tuple[list[str], list[str]]:
    routes = []
    for kind in DiagnosticKind:
        base = _KIND_DISPATCH.get(kind)
        if base:
            routes.append(
                f"| {kind.value} | {base.target_state} | "
                f"{'Yes' if kind in _ESCALATABLE_KINDS else 'No'} | "
                f"{'Yes' if base.create_upstream_revision else 'No'} |"
            )
        else:
            routes.append(f"| {kind.value} | (no dispatch) | — | — |")
    escalatable = [k.value for k in sorted(_ESCALATABLE_KINDS)]
    return routes, escalatable


def extract_role_summaries(prompts_dir: Path | None = None) -> dict[str, str]:
    d = prompts_dir or PROMPTS_DIR
    summaries = {}
    for p in sorted(d.glob("*.md")):
        role = p.stem
        text = p.read_text()
        summary = _extract_first_paragraph(text)
        if summary:
            summaries[role] = summary
    return summaries


def _extract_first_paragraph(text: str) -> str:
    lines = []
    in_content = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            in_content = True
            continue
        if in_content and stripped.startswith("## "):
            break
        if in_content and stripped:
            lines.append(stripped)
    return " ".join(lines).strip()


def format_pipeline_doc(doc: PipelineDoc) -> str:
    lines = ["# Pipeline Documentation (auto-generated)", ""]
    lines.append(f"**Workflow version:** {doc.workflow_version}")
    lines.append("")

    lines.append("## States")
    lines.append("")
    for s in doc.states:
        lines.append(f"- `{s}`")
    lines.append("")

    lines.append("## Work Item Types")
    lines.append("")
    for wit in doc.work_item_types:
        lines.append(f"- `{wit}`")
        fields = doc.custom_fields.get(wit, [])
        if fields:
            for cf in fields:
                lines.append(f"  - `{cf}`")
    lines.append("")

    lines.append("## Roles")
    lines.append("")
    for r in doc.roles:
        lines.append(f"- `{r}`")
    lines.append("")

    lines.append("## Link Types")
    lines.append("")
    for lt in doc.link_types:
        lines.append(f"- `{lt}`")
    lines.append("")

    if doc.stage_handoffs:
        lines.append("## Transitions")
        lines.append("")
        for sh in doc.stage_handoffs:
            lines.append(f"- {sh}")
        lines.append("")

    return "\n".join(lines)


def format_full_doc(
    doc: PipelineDoc,
    router_routes: list[str],
    escalatable: list[str],
    role_summaries: dict[str, str],
) -> str:
    lines = [format_pipeline_doc(doc)]

    lines.append("## Failure Routing Table")
    lines.append("")
    lines.append("| Diagnostic Kind | Target State | Escalatable | Upstream Revision |")
    lines.append("|---|---|---|---|")
    for r in router_routes:
        lines.append(r)
    lines.append("")

    lines.append("## Escalatable Diagnostic Kinds")
    lines.append("")
    for k in escalatable:
        lines.append(f"- `{k}`")
    lines.append("")

    lines.append("## Role Summaries")
    lines.append("")
    for role, summary in sorted(role_summaries.items()):
        lines.append(f"### `{role}`")
        lines.append("")
        lines.append(summary)
        lines.append("")

    return "\n".join(lines)


def generate_full_doc(workflow_path: Path | None = None) -> str:
    if workflow_path is None:
        paths = sorted(WORKFLOWS_DIR.glob("phase*.yaml"))
        workflow_path = paths[-1] if paths else WORKFLOWS_DIR / "phase5.yaml"

    doc = generate_from_workflow(workflow_path)
    router_routes, escalatable = generate_router_table()
    role_summaries = extract_role_summaries()
    return format_full_doc(doc, router_routes, escalatable, role_summaries)
