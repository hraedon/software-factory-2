from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from factory.config import FactoryConfig
from factory.constants import (
    CUSTOM_FIELD_MODULE_NAME,
    CUSTOM_FIELD_SPEC_SECTION,
    STATE_CANNOT_PROCEED,
    STATE_LOCKED,
    UNKNOWN_FALLBACK,
)

_review_log = logging.getLogger("factory.review_surface")


@dataclass(frozen=True)
class CannotProceedDetail:
    module_name: str
    work_item_type: str
    reason: str


@dataclass(frozen=True)
class ModuleReview:
    module_name: str
    status: str
    work_item_id: str
    work_item_type: str
    spec_section_preview: str


@dataclass(frozen=True)
class ReviewReport:
    project_name: str
    pipeline_status: str
    total_items: int
    locked_items: int
    cannot_proceed_items: int
    in_progress_items: int
    modules: list[ModuleReview]
    cannot_proceed_details: list[CannotProceedDetail]


def generate_review_report(config: FactoryConfig) -> ReviewReport:
    from regista import Regista

    sub = Regista(config.dsn, config.project_name, config.hmac_key_path)
    try:
        work_items = sub.query_work_items(
            workflow_name=config.workflow_name,
            workflow_version=config.workflow_version,
        )
    finally:
        sub.close()

    locked = 0
    cannot_proceed = 0
    in_progress = 0
    modules: list[ModuleReview] = []
    cp_details: list[CannotProceedDetail] = []

    for wi in work_items:
        state = wi.current_state
        if state == STATE_LOCKED:
            locked += 1
        elif state == STATE_CANNOT_PROCEED:
            cannot_proceed += 1
        else:
            in_progress += 1

        custom: dict[str, Any] = wi.custom_fields or {}
        module_name = custom.get(CUSTOM_FIELD_MODULE_NAME, wi.work_item_type)
        spec_section = custom.get(CUSTOM_FIELD_SPEC_SECTION, "")
        preview = spec_section[:200] + "..." if len(spec_section) > 200 else spec_section

        modules.append(
            ModuleReview(
                module_name=module_name,
                status=state,
                work_item_id=str(wi.work_item_id),
                work_item_type=wi.work_item_type,
                spec_section_preview=preview,
            )
        )

        if state == STATE_CANNOT_PROCEED:
            diag = custom.get("diagnostics", {})
            if isinstance(diag, dict):
                reason = str(diag.get("rationale", diag.get("reason", UNKNOWN_FALLBACK)))
            else:
                reason = str(diag) if diag else UNKNOWN_FALLBACK
            cp_details.append(
                CannotProceedDetail(
                    module_name=module_name,
                    work_item_type=wi.work_item_type,
                    reason=str(reason),
                )
            )

    if cannot_proceed > 0:
        pipeline_status = "partial"
    elif in_progress > 0:
        pipeline_status = "in_progress"
    else:
        pipeline_status = "complete"

    return ReviewReport(
        project_name=config.project_name,
        pipeline_status=pipeline_status,
        total_items=len(work_items),
        locked_items=locked,
        cannot_proceed_items=cannot_proceed,
        in_progress_items=in_progress,
        modules=modules,
        cannot_proceed_details=cp_details,
    )


def render_review_markdown(report: ReviewReport) -> str:
    lines: list[str] = []
    lines.append(f"# Review Report: {report.project_name}")
    lines.append("")
    lines.append(f"**Status:** {report.pipeline_status}")
    lines.append(
        f"**Items:** {report.total_items} total, "
        f"{report.locked_items} locked, "
        f"{report.cannot_proceed_items} cannot_proceed, "
        f"{report.in_progress_items} in_progress"
    )
    lines.append("")

    if report.pipeline_status == "complete":
        lines.append("## Outcome: All items locked")
        lines.append("")
        lines.append("The pipeline completed successfully. All work items reached locked state.")
        lines.append("Review the artifact bundle and run the software to verify behavior.")
        lines.append("")
    elif report.pipeline_status == "partial":
        lines.append("## Outcome: Partial completion")
        lines.append("")
        lines.append(
            f"{report.cannot_proceed_items} item(s) could not proceed. "
            "Review the details below and decide how to proceed."
        )
        lines.append("")

    lines.append("## Per-module status")
    lines.append("")
    lines.append("| Module | Type | Status |")
    lines.append("|---|---|---|")
    for mod in sorted(report.modules, key=lambda m: (m.status != "locked", m.module_name)):
        lines.append(f"| {mod.module_name} | {mod.work_item_type} | {mod.status} |")
    lines.append("")

    if report.cannot_proceed_details:
        lines.append("## Cannot-proceed details")
        lines.append("")
        for cp in report.cannot_proceed_details:
            lines.append(f"### {cp.module_name} ({cp.work_item_type})")
            lines.append("")
            lines.append(cp.reason)
            lines.append("")

    lines.append("## Next steps")
    lines.append("")
    if report.pipeline_status == "complete":
        lines.append(
            "1. Extract the artifact bundle: "
            "`factory bundle --config <yaml> --output bundle.tar.gz`"
        )
        lines.append("2. Install dependencies: `pip install -r requirements.txt`")
        lines.append("3. Run the software and verify behavior matches your intent")
        lines.append("4. If satisfied, the bundle is ready to ship")
    elif report.pipeline_status == "partial":
        lines.append("1. Review the cannot-proceed items above")
        lines.append("2. For each item, decide: revise the spec and re-run, or accept the gap")
        lines.append(
            "3. To re-run with revised specs: update the spec files "
            "and run `populate_work_items.py --reset`"
        )
    else:
        lines.append("1. The pipeline is still running. Check telemetry for progress.")
        lines.append("2. Use `factory report --config <yaml>` for live status.")

    lines.append("")
    return "\n".join(lines)


def write_review_report(report: ReviewReport, output_path: Path) -> Path:
    output_path.mkdir(parents=True, exist_ok=True)
    md_path = output_path / "REVIEW.md"
    md_path.write_text(render_review_markdown(report))

    json_path = output_path / "review.json"
    json_path.write_text(_report_to_json(report))

    return md_path


def _report_to_json(report: ReviewReport) -> str:
    data = {
        "project_name": report.project_name,
        "pipeline_status": report.pipeline_status,
        "total_items": report.total_items,
        "locked_items": report.locked_items,
        "cannot_proceed_items": report.cannot_proceed_items,
        "in_progress_items": report.in_progress_items,
        "modules": [
            {
                "module_name": m.module_name,
                "status": m.status,
                "work_item_id": m.work_item_id,
                "work_item_type": m.work_item_type,
            }
            for m in report.modules
        ],
        "cannot_proceed_details": [
            {
                "module_name": cp.module_name,
                "work_item_type": cp.work_item_type,
                "reason": cp.reason,
            }
            for cp in report.cannot_proceed_details
        ],
    }
    return json.dumps(data, indent=2)
