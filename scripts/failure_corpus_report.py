from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path

CORPUS_DIR = Path(__file__).resolve().parent.parent / "runs" / "_corpus"
CORPUS_PATH = CORPUS_DIR / "inner_gate_failures.jsonl"
REPORT_DIR = Path(__file__).resolve().parent.parent / ".factory" / "analysis"

CATEGORY_ORDER = [
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
]

TREND_WINDOW = 3


def load_corpus(path: Path) -> list[dict]:
    rows: list[dict] = []
    if not path.exists():
        return rows
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def _sort_gr_ids(gr_ids: set[str]) -> list[str]:
    def _key(gr: str) -> tuple[int, str]:
        import re

        m = re.match(r"GR-(\d+)(\w*)", gr)
        if m:
            return int(m.group(1)), m.group(2)
        return 999, gr

    return sorted(gr_ids, key=_key)


def _extract_gr_number(gr_id: str) -> int:
    import re

    m = re.match(r"GR-(\d+)", gr_id)
    return int(m.group(1)) if m else 0


def compute_trend(
    by_gr_cat: dict[str, dict[str, int]],
    sorted_grs: list[str],
    category: str,
) -> str:
    counts = []
    for gr in sorted_grs:
        cat_counts = by_gr_cat.get(gr, {})
        total_in_gr = sum(cat_counts.values())
        cat_count = cat_counts.get(category, 0)
        if total_in_gr > 0:
            counts.append(cat_count / total_in_gr)
        else:
            counts.append(0.0)

    if len(counts) < 2:
        return "  "

    recent = counts[-TREND_WINDOW:]
    prior = counts[: -TREND_WINDOW] if len(counts) > TREND_WINDOW else counts[:-1]

    if not prior:
        return "  "

    recent_avg = sum(recent) / len(recent)
    prior_avg = sum(prior) / len(prior)

    diff = recent_avg - prior_avg
    if diff > 0.05:
        return "\u2191\u2191"
    elif diff > 0.02:
        return "\u2191"
    elif diff < -0.05:
        return "\u2193\u2193"
    elif diff < -0.02:
        return "\u2193"
    return "\u2192"


def generate_report(rows: list[dict]) -> str:
    if not rows:
        return "No classified rows in corpus."

    classified = [r for r in rows if r.get("category")]
    if not classified:
        return "No classified rows in corpus."

    gr_ids = set(r["gr_id"] for r in rows)
    sorted_grs = _sort_gr_ids(gr_ids)
    n = len(rows)

    by_category: dict[str, int] = defaultdict(int)
    by_gr_cat: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for r in classified:
        cat = r["category"]
        by_category[cat] += 1
        by_gr_cat[r["gr_id"]][cat] += 1

    lines: list[str] = []
    lines.append(f"# Inner-gate failure corpus \u2014 N={n} ({sorted_grs[0]} through {sorted_grs[-1]})")
    lines.append("")
    lines.append(f"Classified: {len(classified)}/{n}")
    lines.append(f"GRs: {', '.join(sorted_grs)}")
    lines.append("")

    lines.append("## Distribution")
    lines.append("")
    lines.append(f"| {'Category':30s} | {'Count':>5s} | {'%':>5s} | {'Trend':>6s} |")
    lines.append(f"|{'-' * 32}|{'-' * 7}|{'-' * 7}|{'-' * 8}|")

    for cat in CATEGORY_ORDER:
        count = by_category.get(cat, 0)
        pct = f"{count / len(classified) * 100:.0f}%" if classified else "0%"
        trend = compute_trend(dict(by_gr_cat), sorted_grs, cat)
        lines.append(f"| {cat:30s} | {count:5d} | {pct:>5s} | {trend:>6s} |")

    other_count = sum(v for k, v in by_category.items() if k not in set(CATEGORY_ORDER))
    if other_count > 0:
        pct = f"{other_count / len(classified) * 100:.0f}%"
        lines.append(f"| {'(uncategorized others)':30s} | {other_count:5d} | {pct:>5s} |       |")

    lines.append("")

    sorted_by_count = sorted(by_category.items(), key=lambda x: -x[1])
    growing = []
    shrinking = []
    for cat, _count in sorted_by_count:
        trend = compute_trend(dict(by_gr_cat), sorted_grs, cat)
        if "\u2191" in trend:
            growing.append(cat)
        elif "\u2193" in trend:
            shrinking.append(cat)

    if growing:
        lines.append("## Top growing categories")
        for cat in growing[:5]:
            count = by_category.get(cat, 0)
            pct = f"{count / len(classified) * 100:.0f}%"
            lines.append(f"1. {cat} \u2014 {pct} of classified failures")
        lines.append("")

    if shrinking:
        lines.append("## Top shrinking categories")
        for cat in shrinking[:5]:
            count = by_category.get(cat, 0)
            pct = f"{count / len(classified) * 100:.0f}%"
            lines.append(f"1. {cat} \u2014 {pct} of classified failures")
        lines.append("")

    unclassified_count = len(rows) - len(classified)
    other_share = by_category.get("other", 0) / len(classified) if classified else 0
    if other_share > 0.10:
        lines.append("## Warning")
        lines.append(
            f"'other' category is {other_share:.0%} of classified rows. "
            "Taxonomy may need revision."
        )
        lines.append("")

    lines.append("## Per-GR breakdown")
    lines.append("")
    header_grs = sorted_grs[-6:]
    gr_header = f"| {'Category':30s} | " + " | ".join(f"{gr:>6s}" for gr in header_grs) + " |"
    gr_sep = f"|{'-' * 32}|" + "|".join("-" * 8 for _ in header_grs) + "|"
    lines.append(gr_header)
    lines.append(gr_sep)
    for cat in CATEGORY_ORDER:
        counts = []
        for gr in header_grs:
            c = by_gr_cat.get(gr, {}).get(cat, 0)
            counts.append(f"{c:6d}")
        lines.append(f"| {cat:30s} | " + " | ".join(counts) + " |")
    lines.append("")

    return "\n".join(lines)


def _main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate failure corpus report")
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output path (default: .factory/analysis/failure-corpus-latest.md)",
    )
    args = parser.parse_args(argv)

    rows = load_corpus(CORPUS_PATH)
    report = generate_report(rows)

    if args.output:
        out_path = Path(args.output)
    else:
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        out_path = REPORT_DIR / "failure-corpus-latest.md"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report)
    print(f"Report written to {out_path}")
    print(report)


def main() -> None:
    _main()


if __name__ == "__main__":
    main()
