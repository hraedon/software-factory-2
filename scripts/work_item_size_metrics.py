from __future__ import annotations

import argparse
import csv
import io
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from substrate import Substrate

from factory.config import FactoryConfig, load_config
from factory.constants import (
    CUSTOM_FIELD_AC_IDS,
    CUSTOM_FIELD_ARTIFACT_PATH,
    CUSTOM_FIELD_DEPENDENCY_REFS,
    CUSTOM_FIELD_SPEC_SECTION,
    STATE_IN_PROGRESS,
    STATE_LOCKED,
    TRANSITION_GATE_FAIL,
    TRANSITION_GATE_PASS,
    TRANSITION_SUBMIT,
)


@dataclass(frozen=True)
class SizeRow:
    gr_id: str
    work_item_id: str
    role: str
    ac_count: int
    spec_word_count: int
    dep_count: int
    dep_total_pyi_lines: int
    first_attempt_passed: bool
    retry_count: int
    gate_label_on_first_fail: str
    locked: bool


def _extract_gr_id(config_path: str) -> str:
    m = re.search(r"golden-run-(\d+\w*)", Path(config_path).stem)
    if m:
        return f"GR-{m.group(1)}"
    return Path(config_path).stem


def _count_acs(spec_section: str) -> int:
    if not spec_section:
        return 0
    heading_count = 0
    bullet_count = 0
    in_ac_section = False
    for line in spec_section.splitlines():
        stripped = line.strip()
        if stripped.lower().startswith("## acceptance criteria"):
            in_ac_section = True
            continue
        if in_ac_section and stripped.startswith("## "):
            break
        if in_ac_section and stripped.startswith("- "):
            bullet_count += 1
        if re.match(r"^## AC-\d+", stripped, re.IGNORECASE):
            heading_count += 1
    return max(heading_count, bullet_count)


def _word_count(text: str) -> int:
    if not text:
        return 0
    return len(text.split())


def _count_dep_lines(sub: Substrate, dep_refs: list[str]) -> tuple[int, int]:
    if not dep_refs:
        return 0, 0
    dep_count = 0
    total_lines = 0
    for ref in dep_refs:
        try:
            from uuid import UUID

            ref_wi = sub.get_work_item(UUID(ref))
        except Exception:
            continue
        if not ref_wi or not ref_wi.custom_fields:
            continue
        artifact_path = ref_wi.custom_fields.get(CUSTOM_FIELD_ARTIFACT_PATH)
        if artifact_path:
            p = Path(artifact_path)
            if p.exists():
                dep_count += 1
                total_lines += len(p.read_text().splitlines())
    return dep_count, total_lines


def _get_gate_events(sub: Substrate, work_item_id: str, event_limit: int) -> list[dict]:
    events = sub.read_events(work_item_id=work_item_id, limit=event_limit)
    gate_events = []
    for ev in events:
        if ev.transition in (TRANSITION_GATE_PASS, TRANSITION_GATE_FAIL):
            meta = ev.actor_metadata or {}
            payload = ev.payload or {}
            gate_name = meta.get("gate_name") or payload.get("diagnostics", {}).get("gate_name", "")
            gate_events.append(
                {
                    "attempt_n": meta.get("attempt_n", 0) or 0,
                    "gate_name": gate_name,
                    "passed": ev.transition == TRANSITION_GATE_PASS,
                    "role": meta.get("role", "unknown"),
                    "channel": meta.get("channel", "unknown"),
                }
            )
    return gate_events


_INNER_GATE_RE = re.compile(
    r"inner_gate_(?P<kind>passed|failed_retry|exhausted_retries).*?work_item_id=(?P<wi>[a-f0-9-]+)"
)

# The structured runner log contains per-gate boolean flags, e.g.:
# mypy_passed=False pytest_passed=True retry=0 ruff_passed=True work_item_id=...
_INNER_GATE_FLAG_RE = re.compile(
    r"(?P<flag>(?:mypy_passed|ruff_passed|pytest_passed|imports_symbols_passed))=(?P<val>True|False)"
)


def _gate_label_from_flags(line: str) -> str:
    flags = {}
    for m in _INNER_GATE_FLAG_RE.finditer(line):
        flags[m.group("flag")] = m.group("val") == "True"
    if flags.get("mypy_passed") is False:
        return "inner_mypy"
    if flags.get("ruff_passed") is False:
        return "inner_ruff"
    if flags.get("pytest_passed") is False:
        return "inner_pytest"
    if flags.get("imports_symbols_passed") is False:
        return "inner_import_symbols"
    # pre_gate_interface_spec uses _run_import_check, which does not emit a
    # structured flag. When all flags are True but diagnostics contain a
    # Traceback, the failure is an import check failure.
    diag_match = re.search(r"diagnostics=\[(?P<diag>.*?)\]", line)
    if diag_match:
        diag_text = diag_match.group("diag")
        if "Traceback" in diag_text or "ModuleNotFound" in diag_text:
            return "inner_import_check"
    return "inner_unknown"


def _parse_runner_log(runner_log_path: str) -> dict[str, dict]:
    """Return map of work_item_id -> {first_attempt_passed, retry_count, gate_label_on_first_fail}"""
    p = Path(runner_log_path)
    if not p.exists():
        return {}
    results: dict[str, dict] = {}
    for line in p.read_text().splitlines():
        m = _INNER_GATE_RE.search(line)
        if not m:
            continue
        kind = m.group("kind")
        wi = m.group("wi")
        if wi not in results:
            results[wi] = {"first_attempt_passed": None, "retry_count": 0, "gate_label_on_first_fail": ""}
        if kind == "passed":
            if results[wi]["first_attempt_passed"] is None:
                results[wi]["first_attempt_passed"] = True
        elif kind == "failed_retry":
            if results[wi]["first_attempt_passed"] is None:
                results[wi]["first_attempt_passed"] = False
            # Extract retry count and gate label from structured flags
            retry_match = re.search(r"retry=(?P<retry>\d+)", line)
            retry = int(retry_match.group("retry")) if retry_match else 0
            gate_label = _gate_label_from_flags(line)
            if retry == 0 and not results[wi]["gate_label_on_first_fail"]:
                results[wi]["gate_label_on_first_fail"] = gate_label
            results[wi]["retry_count"] = max(results[wi]["retry_count"], retry + 1)
        elif kind == "exhausted_retries":
            results[wi]["retry_count"] = max(results[wi].get("retry_count", 0), 2)
    # For items with no inner gate events but were submitted, infer passed
    for wi in results:
        if results[wi]["first_attempt_passed"] is None:
            results[wi]["first_attempt_passed"] = True
    return results


def extract_size_rows(
    config: FactoryConfig,
    gr_id: str,
    runner_log_path: str | None = None,
) -> list[SizeRow]:
    sub = Substrate(config.dsn, config.project_name, config.hmac_key_path)
    try:
        page = sub.query_work_items(
            workflow_name=config.workflow_name,
            workflow_version=config.workflow_version,
            page_size=config.query_page_size,
        )
        rows: list[SizeRow] = []
        for wi in page.items:
            custom = wi.custom_fields or {}
            work_item_id = str(wi.work_item_id)

            spec_section = custom.get(CUSTOM_FIELD_SPEC_SECTION, "")
            ac_ids_raw = custom.get(CUSTOM_FIELD_AC_IDS, [])
            ac_ids = ac_ids_raw if isinstance(ac_ids_raw, list) else [ac_ids_raw]

            dep_refs_raw = custom.get(CUSTOM_FIELD_DEPENDENCY_REFS) or []
            if isinstance(dep_refs_raw, str):
                dep_refs_raw = [dep_refs_raw]

            dep_count, dep_lines = _count_dep_lines(sub, dep_refs_raw)

            ac_count = _count_acs(spec_section)
            if ac_count == 0 and ac_ids:
                ac_count = len(ac_ids)

            spec_words = _word_count(spec_section)

            gate_events = _get_gate_events(sub, work_item_id, config.telemetry_event_limit)

            submit_events = [
                ev
                for ev in sub.read_events(
                    work_item_id=work_item_id, limit=config.telemetry_event_limit
                )
                if ev.transition == TRANSITION_SUBMIT
            ]
            role = "unknown"
            if submit_events:
                meta = submit_events[-1].actor_metadata or {}
                role = meta.get("role", "unknown")

            inner_gate_events = [
                ge
                for ge in gate_events
                if ge["gate_name"].startswith("inner_")
                or ge["gate_name"]
                in (
                    "inner_mypy",
                    "inner_ruff",
                    "inner_pytest",
                    "inner_import",
                    "inner_test_collect",
                    "inner_import_symbols",
                )
            ]

            first_attempt_passed = False
            retry_count = 0
            gate_label_on_first_fail = ""

            # Prefer runner log for accurate inner-gate first-attempt signal
            log_results = _parse_runner_log(runner_log_path or "")
            log_result = log_results.get(work_item_id)
            if log_result:
                first_attempt_passed = log_result["first_attempt_passed"]
                retry_count = log_result["retry_count"]
                gate_label_on_first_fail = log_result["gate_label_on_first_fail"]
            elif not inner_gate_events:
                first_attempt_passed = True
                retry_count = 0
            else:
                sorted_events = sorted(inner_gate_events, key=lambda g: g["attempt_n"])
                first_events = [ge for ge in sorted_events if ge["attempt_n"] <= 1]
                if first_events:
                    if all(ge["passed"] for ge in first_events):
                        first_attempt_passed = True
                    else:
                        first_attempt_passed = False
                        for ge in first_events:
                            if not ge["passed"]:
                                gate_label_on_first_fail = ge["gate_name"]
                                break
                else:
                    first_attempt_passed = True

                attempts_seen = set(ge["attempt_n"] for ge in inner_gate_events)
                retry_count = max(0, len(attempts_seen) - 1)

            locked = wi.current_state == STATE_LOCKED

            rows.append(
                SizeRow(
                    gr_id=gr_id,
                    work_item_id=work_item_id,
                    role=role,
                    ac_count=ac_count,
                    spec_word_count=spec_words,
                    dep_count=dep_count,
                    dep_total_pyi_lines=dep_lines,
                    first_attempt_passed=first_attempt_passed,
                    retry_count=retry_count,
                    gate_label_on_first_fail=gate_label_on_first_fail,
                    locked=locked,
                )
            )
        return rows
    finally:
        sub.close()


def rows_to_csv(rows: list[SizeRow]) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "gr_id",
            "work_item_id",
            "role",
            "ac_count",
            "spec_word_count",
            "dep_count",
            "dep_total_pyi_lines",
            "first_attempt_passed",
            "retry_count",
            "gate_label_on_first_fail",
            "locked",
        ]
    )
    for r in rows:
        writer.writerow(
            [
                r.gr_id,
                r.work_item_id,
                r.role,
                r.ac_count,
                r.spec_word_count,
                r.dep_count,
                r.dep_total_pyi_lines,
                r.first_attempt_passed,
                r.retry_count,
                r.gate_label_on_first_fail,
                r.locked,
            ]
        )
    return buf.getvalue()


def _main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Extract work-item size metrics")
    parser.add_argument("--config", type=str, nargs="*", help="Config YAML(s)")
    parser.add_argument("--output", type=str, default=None, help="Output CSV path")
    parser.add_argument("--runner-log", type=str, nargs="*", help="Runner log path(s) (same order as --config)")
    args = parser.parse_args(argv)

    if not args.config:
        parser.error("--config required")

    all_rows: list[SizeRow] = []
    for idx, config_path in enumerate(args.config):
        gr_id = _extract_gr_id(config_path)
        print(f"Extracting {gr_id}...")
        try:
            config = load_config(config_path)
        except Exception as e:
            print(f"  SKIP: {e}")
            continue
        runner_log = ""
        if args.runner_log and idx < len(args.runner_log):
            runner_log = args.runner_log[idx]
        try:
            rows = extract_size_rows(config, gr_id, runner_log_path=runner_log or None)
        except Exception as e:
            print(f"  SKIP: {e}")
            continue
        print(f"  {len(rows)} work items")
        all_rows.extend(rows)

    csv_text = rows_to_csv(all_rows)
    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        Path(args.output).write_text(csv_text)
        print(f"Wrote {len(all_rows)} rows to {args.output}")
    else:
        print(csv_text)


def main() -> None:
    _main()


if __name__ == "__main__":
    main()
