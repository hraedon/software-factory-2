from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

import yaml
from substrate import Substrate

from factory.config import FactoryConfig, load_config
from factory.constants import (
    GATE_NAME_INNER_COLLECT,
    GATE_NAME_INNER_IMPORT,
    GATE_NAME_INNER_IMPORT_SYMBOLS,
    GATE_NAME_INNER_MYPY,
    GATE_NAME_INNER_PYTEST,
    GATE_NAME_INNER_RUFF,
    TRANSITION_CHANNEL_FAIL,
    TRANSITION_GATE_FAIL,
)
from factory.failure_summary import derive_failures

CORPUS_DIR = Path(__file__).resolve().parent.parent / "runs" / "_corpus"
CORPUS_PATH = CORPUS_DIR / "inner_gate_failures.jsonl"
RULES_PATH = CORPUS_DIR / "classification_rules.yaml"
FEEDBACK_EXCERPT_LIMIT = 500

INNER_GATE_NAMES = frozenset(
    {
        GATE_NAME_INNER_RUFF,
        GATE_NAME_INNER_MYPY,
        GATE_NAME_INNER_PYTEST,
        GATE_NAME_INNER_IMPORT,
        GATE_NAME_INNER_COLLECT,
        GATE_NAME_INNER_IMPORT_SYMBOLS,
    }
)

VALID_CATEGORIES = frozenset(
    {
        "ruff_style",
        "import_unknown_symbol",
        "import_module_path",
        "type_mismatch_library_api",
        "type_mismatch_internal",
        "mypy_missing_annotation",
        "pytest_assertion",
        "pytest_collect_error",
        "pytest_fixture_missing",
        "spec_ambiguity",
        "channel_failure",
        "other",
    }
)


@dataclass(frozen=True)
class CorpusRow:
    gr_id: str
    work_item_id: str
    role: str
    channel: str
    attempt: int
    gate_label: str
    feedback_excerpt: str
    category: str | None
    subcategory: str | None
    fixed_on_retry: int | None
    fixed_on_retry_label: str | None
    model: str | None
    ts: str | None

    def to_dict(self) -> dict:
        return asdict(self)


def _extract_gr_id(config_path: str) -> str:
    stem = Path(config_path).stem
    import re

    m = re.search(r"golden-run-(\d+\w*)", stem)
    if m:
        return f"GR-{m.group(1)}"
    return stem


def _load_rules() -> list[tuple[re.Pattern, str]]:
    if not RULES_PATH.exists():
        return []
    with open(RULES_PATH) as f:
        data = yaml.safe_load(f)
    rules = []
    for entry in data.get("allowed", []):
        pat = entry.get("pattern", "")
        cat = entry.get("category", "other")
        try:
            rules.append((re.compile(pat, re.IGNORECASE), cat))
        except re.error:
            continue
    return rules


def _classify_auto(feedback: str, rules: list[tuple[re.Pattern, str]]) -> str | None:
    for pattern, category in rules:
        if pattern.search(feedback):
            return category
    return None


def _load_existing_keys(path: Path) -> set[tuple[str, str, int, str]]:
    keys: set[tuple[str, str, int, str]] = set()
    if not path.exists():
        return keys
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
                keys.add((row["gr_id"], row["work_item_id"], row["attempt"], row["gate_label"]))
            except (json.JSONDecodeError, KeyError):
                continue
    return keys


def _find_fixed_on_retry(
    failures_after: list,
    gate_label: str,
) -> tuple[int | None, str | None]:
    for f in failures_after:
        if f.gate_name != gate_label:
            fixed_label = f.gate_name
            return f.attempt_number, fixed_label
    return None, None


def extract_from_config(
    config: FactoryConfig,
    gr_id: str,
    rules: list[tuple[re.Pattern, str]],
    existing_keys: set[tuple[str, str, int, str]],
) -> list[CorpusRow]:
    sub = Substrate(config.dsn, config.project_name, config.hmac_key_path)
    try:
        page = sub.query_work_items(
            workflow_name=config.workflow_name,
            workflow_version=config.workflow_version,
            page_size=config.query_page_size,
        )
        rows: list[CorpusRow] = []
        for wi in page.items:
            work_item_id = str(wi.work_item_id)
            failures = derive_failures(sub, work_item_id)

            inner_failures = [
                f for f in failures if f.gate_name in INNER_GATE_NAMES and f.failure_type == TRANSITION_GATE_FAIL
            ]

            first_inner_failures: dict[str, object] = {}
            for f in inner_failures:
                key = f.gate_name
                if key not in first_inner_failures:
                    first_inner_failures[key] = f

            for gate_name, first_fail in first_inner_failures.items():
                f = first_fail
                attempt = f.attempt_number

                corpus_key = (gr_id, work_item_id, attempt, gate_name)
                if corpus_key in existing_keys:
                    continue

                feedback = f.diagnostic or f.gate_output or ""
                excerpt = feedback[:FEEDBACK_EXCERPT_LIMIT]

                later_failures = [
                    lf for lf in inner_failures if lf.attempt_number > attempt
                ]

                passed_later = len(later_failures) < len(inner_failures) - len(
                    [lf for lf in inner_failures if lf.gate_name == gate_name]
                )
                fixed_on = None
                fixed_label = None
                if passed_later:
                    remaining = [lf for lf in later_failures if lf.gate_name != gate_name]
                    if remaining:
                        fixed_on = remaining[0].attempt_number
                        fixed_label = remaining[0].gate_name
                    else:
                        fixed_on = attempt + 1

                category = _classify_auto(feedback, rules)

                meta = f.actor_metadata or {}
                model = meta.get("model")

                ts = None
                if hasattr(f, "_event_ts"):
                    ts = f._event_ts

                rows.append(
                    CorpusRow(
                        gr_id=gr_id,
                        work_item_id=work_item_id,
                        role=f.role,
                        channel=f.channel,
                        attempt=attempt,
                        gate_label=gate_name,
                        feedback_excerpt=excerpt,
                        category=category,
                        subcategory=None,
                        fixed_on_retry=fixed_on,
                        fixed_on_retry_label=fixed_label,
                        model=model,
                        ts=ts,
                    )
                )
        return rows
    finally:
        sub.close()


def append_rows(path: Path, rows: list[CorpusRow]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with open(path, "a") as f:
        for row in rows:
            f.write(json.dumps(row.to_dict(), sort_keys=True) + "\n")
            count += 1
    return count


def classify_interactive(path: Path) -> None:
    unclassified: list[tuple[int, dict]] = []
    if not path.exists():
        print("No corpus file found.")
        return
    with open(path) as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("category") is None:
                unclassified.append((i, row))

    if not unclassified:
        print("All rows classified.")
        return

    print(f"\n{len(unclassified)} unclassified rows.\n")
    categories = sorted(VALID_CATEGORIES)

    lines_all: list[str] = []
    with open(path) as f:
        lines_all = f.readlines()

    for line_no, row in unclassified:
        print(f"--- Row {line_no} ---")
        print(f"  GR:          {row['gr_id']}")
        print(f"  Work item:   {row['work_item_id'][:8]}...")
        print(f"  Role:        {row['role']}")
        print(f"  Gate:        {row['gate_label']}")
        print(f"  Feedback:    {row['feedback_excerpt'][:200]}")
        print()

        for idx, cat in enumerate(categories, 1):
            print(f"  {idx:2d}. {cat}")
        print()

        choice = input("Category (number or name, Enter=skip, q=quit): ").strip()
        if choice == "q":
            break
        if not choice:
            continue

        selected = None
        if choice.isdigit():
            idx = int(choice) - 1
            if 0 <= idx < len(categories):
                selected = categories[idx]
        elif choice in VALID_CATEGORIES:
            selected = choice

        if selected:
            row["category"] = selected
            lines_all[line_no - 1] = json.dumps(row, sort_keys=True) + "\n"
            print(f"  -> {selected}\n")

    with open(path, "w") as f:
        f.writelines(lines_all)
    print("Classification saved.")


def _main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build inner-gate failure corpus")
    parser.add_argument("--config", type=str, nargs="*", help="Config YAML(s) to extract from")
    parser.add_argument("--classify", action="store_true", help="Interactive classification")
    parser.add_argument("--status", action="store_true", help="Print corpus statistics")
    args = parser.parse_args(argv)

    if args.status:
        _print_status()
        return

    if args.classify:
        classify_interactive(CORPUS_PATH)
        return

    if not args.config:
        parser.error("--config, --classify, or --status required")

    rules = _load_rules()
    existing_keys = _load_existing_keys(CORPUS_PATH)
    total_new = 0

    for config_path in args.config:
        gr_id = _extract_gr_id(config_path)
        print(f"Extracting from {gr_id} ({config_path})...")
        try:
            config = load_config(config_path)
        except Exception as e:
            print(f"  SKIP: cannot load config: {e}")
            continue

        try:
            rows = extract_from_config(config, gr_id, rules, existing_keys)
        except Exception as e:
            print(f"  SKIP: extraction failed: {e}")
            continue

        if rows:
            count = append_rows(CORPUS_PATH, rows)
            for r in rows:
                existing_keys.add((r.gr_id, r.work_item_id, r.attempt, r.gate_label))
            print(f"  {count} new rows appended.")
            total_new += count
        else:
            print("  No new rows.")

    print(f"\nTotal new rows: {total_new}")
    print(f"Corpus: {CORPUS_PATH}")


def _print_status() -> None:
    if not CORPUS_PATH.exists():
        print("Corpus is empty.")
        return
    total = 0
    classified = 0
    by_category: dict[str, int] = {}
    by_gr: dict[str, int] = {}
    with open(CORPUS_PATH) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            total += 1
            cat = row.get("category")
            if cat:
                classified += 1
                by_category[cat] = by_category.get(cat, 0) + 1
            gr = row.get("gr_id", "unknown")
            by_gr[gr] = by_gr.get(gr, 0) + 1

    print(f"Total rows:       {total}")
    print(f"Classified:       {classified}")
    print(f"Unclassified:     {total - classified}")
    print(f"GRs:              {', '.join(sorted(by_gr))}")
    if by_category:
        print("\nBy category:")
        for cat in sorted(by_category):
            print(f"  {cat:30s} {by_category[cat]:4d}")


def main() -> None:
    _main()


if __name__ == "__main__":
    main()
